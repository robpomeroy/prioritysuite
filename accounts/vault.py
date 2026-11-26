import base64
import json
import logging
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.dateparse import parse_datetime

from decisions.models import DecisionRecord, LLMReflectionLog
from frameworks.models import Domain, Framework, Goal, Objective, StatusChoices, Why

logger = logging.getLogger(__name__)

# PBKDF2 iterations: default for new backups is 600,000 (OWASP recommended for SHA-256).
# Allowed iterations on restore are strictly bounded to prevent arbitrary compute exhaustion.
DEFAULT_PBKDF2_ITERATIONS = 600_000
ALLOWED_PBKDF2_ITERATIONS = {100_000, 480_000, 600_000}

# Maximum unencrypted vault payload size: 10 MiB.
# Encrypted Fernet ciphertext + base64 + JSON envelope will remain well under
# Nginx's 20 MiB client_max_body_size cap.
MAX_RAW_VAULT_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_ENCRYPTED_VAULT_BYTES = 18 * 1024 * 1024  # 18 MiB


def derive_vault_key(
    password: str, salt: bytes, iterations: int = DEFAULT_PBKDF2_ITERATIONS
) -> bytes:
    """Derives a 32-byte url-safe base64 key from password and salt using PBKDF2-HMAC-SHA256."""
    if iterations not in ALLOWED_PBKDF2_ITERATIONS:
        raise ValueError(f"Unsupported PBKDF2 iteration count: {iterations}")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def serialize_user_data(user: User) -> dict[str, Any]:
    """Serializes all private frameworks, domains, whys, objectives, goals,

    decisions, and reflection logs for the given user within an atomic transaction.
    """
    frameworks_data = []

    with transaction.atomic():
        for fw in (
            Framework.objects.filter(owner=user)
            .select_related("owner")
            .prefetch_related(
                "domains__whys",
                "domains__primary_objectives__whys",
                "domains__primary_objectives__related_domains",
                "domains__primary_goals__objectives",
                "domains__primary_goals__related_domains",
                "decisions__affected_domains",
                "decisions__relevant_whys",
                "decisions__supporting_objectives",
                "decisions__conflicting_objectives",
                "reflections",
            )
        ):
            domains_list = []
            framework_domain_ids = set()
            for d in fw.domains.all():
                framework_domain_ids.add(d.id)

            for d in fw.domains.all():
                whys_list = []
                for w in d.whys.all():
                    whys_list.append(
                        {
                            "export_id": str(w.id),
                            "title": w.title,
                            "description": w.description,
                            "is_non_negotiable": w.is_non_negotiable,
                            "display_order": w.display_order,
                            "last_reviewed_at": (
                                w.last_reviewed_at.isoformat() if w.last_reviewed_at else None
                            ),
                        }
                    )

                objectives_list = []
                for obj in d.primary_objectives.all():
                    # Ensure referenced related domains are part of this framework export
                    valid_related_domains = [
                        rd for rd in obj.related_domains.all() if rd.id in framework_domain_ids
                    ]
                    objectives_list.append(
                        {
                            "export_id": str(obj.id),
                            "title": obj.title,
                            "description": obj.description,
                            "status": obj.status,
                            "whys": [w.title for w in obj.whys.all()],
                            "why_ids": [str(w.id) for w in obj.whys.all()],
                            "related_domains": [rd.name for rd in valid_related_domains],
                            "related_domain_ids": [str(rd.id) for rd in valid_related_domains],
                            "last_reviewed_at": (
                                obj.last_reviewed_at.isoformat() if obj.last_reviewed_at else None
                            ),
                        }
                    )

                goals_list = []
                for g in d.primary_goals.all():
                    valid_goal_rds = [
                        rd for rd in g.related_domains.all() if rd.id in framework_domain_ids
                    ]
                    goals_list.append(
                        {
                            "export_id": str(g.id),
                            "title": g.title,
                            "description": g.description,
                            "status": g.status,
                            "target_date": g.target_date.isoformat() if g.target_date else None,
                            "objectives": [o.title for o in g.objectives.all()],
                            "objective_ids": [str(o.id) for o in g.objectives.all()],
                            "related_domains": [rd.name for rd in valid_goal_rds],
                            "related_domain_ids": [str(rd.id) for rd in valid_goal_rds],
                            "last_reviewed_at": (
                                g.last_reviewed_at.isoformat() if g.last_reviewed_at else None
                            ),
                        }
                    )

                domains_list.append(
                    {
                        "export_id": str(d.id),
                        "name": d.name,
                        "description": d.description,
                        "display_order": d.display_order,
                        "whys": whys_list,
                        "objectives": objectives_list,
                        "goals": goals_list,
                    }
                )

            decisions_list = []
            for dec in fw.decisions.all():
                valid_dec_domains = [
                    ad for ad in dec.affected_domains.all() if ad.id in framework_domain_ids
                ]
                decisions_list.append(
                    {
                        "export_id": str(dec.id),
                        "title": dec.title,
                        "proposal_description": dec.proposal_description,
                        "benefits_and_costs": dec.benefits_and_costs,
                        "alternatives_considered": dec.alternatives_considered,
                        "unresolved_questions": dec.unresolved_questions,
                        "decision_outcome": dec.decision_outcome,
                        "status": dec.status,
                        "created_at": dec.created_at.isoformat() if dec.created_at else None,
                        "affected_domains": [ad.name for ad in valid_dec_domains],
                        "affected_domain_ids": [str(ad.id) for ad in valid_dec_domains],
                        "relevant_whys": [rw.title for rw in dec.relevant_whys.all()],
                        "relevant_why_ids": [str(rw.id) for rw in dec.relevant_whys.all()],
                        "supporting_objectives": [
                            so.title for so in dec.supporting_objectives.all()
                        ],
                        "supporting_objective_ids": [
                            str(so.id) for so in dec.supporting_objectives.all()
                        ],
                        "conflicting_objectives": [
                            co.title for co in dec.conflicting_objectives.all()
                        ],
                        "conflicting_objective_ids": [
                            str(co.id) for co in dec.conflicting_objectives.all()
                        ],
                    }
                )

            reflections_list = []
            for ref in fw.reflections.all():
                reflections_list.append(
                    {
                        "decision_title": ref.decision.title if ref.decision else None,
                        "decision_id": str(ref.decision.id) if ref.decision else None,
                        "user_prompt": ref.user_prompt,
                        "context_snapshot": ref.context_snapshot,
                        "llm_response": ref.llm_response,
                        "provider_used": ref.provider_used,
                        "created_at": ref.created_at.isoformat() if ref.created_at else None,
                    }
                )

            frameworks_data.append(
                {
                    "export_id": str(fw.id),
                    "name": fw.name,
                    "description": fw.description,
                    "is_sample": fw.is_sample,
                    "domains": domains_list,
                    "decisions": decisions_list,
                    "reflections": reflections_list,
                }
            )

    return {
        "version": "1.0",
        "username": user.username,
        "frameworks": frameworks_data,
    }


def create_encrypted_vault_payload(user: User, password: str) -> dict[str, Any]:
    """Generates a password-encrypted vault backup envelope with PBKDF2-derived key."""
    salt = os.urandom(16)
    key = derive_vault_key(password, salt, iterations=DEFAULT_PBKDF2_ITERATIONS)
    cipher = Fernet(key)

    data = serialize_user_data(user)
    raw_json = json.dumps(data, indent=2).encode("utf-8")
    if len(raw_json) > MAX_RAW_VAULT_BYTES:
        raise ValueError(
            f"Vault data size ({len(raw_json)} bytes) exceeds the maximum allowed export size "
            f"({MAX_RAW_VAULT_BYTES} bytes)."
        )

    ciphertext = cipher.encrypt(raw_json).decode("utf-8")

    return {
        "format": "prioritysuite-encrypted-vault-v1",
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": DEFAULT_PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("utf-8"),
        "ciphertext": ciphertext,
    }


def _validate_vault_data(data: dict[str, Any]) -> None:
    """Validates structure and data types of decrypted vault data before DB writes."""
    if not isinstance(data, dict):
        raise ValueError("Decrypted vault payload must be a JSON dictionary.")

    frameworks = data.get("frameworks")
    if not isinstance(frameworks, list):
        raise ValueError("Vault payload 'frameworks' field must be a list.")

    for fw in frameworks:
        if not isinstance(fw, dict):
            raise ValueError("Framework entry in vault payload must be a dictionary.")

        domains = fw.get("domains", [])
        if not isinstance(domains, list):
            raise ValueError(f"Domains list in framework '{fw.get('name')}' must be a list.")

        for d in domains:
            if not isinstance(d, dict):
                raise ValueError("Domain entry must be a dictionary.")

            # Validate whys
            whys = d.get("whys", [])
            if not isinstance(whys, list):
                raise ValueError(f"Whys in domain '{d.get('name')}' must be a list.")
            for w in whys:
                if not isinstance(w, dict):
                    raise ValueError("Why entry must be a dictionary.")

            # Validate objectives
            objectives = d.get("objectives", [])
            if not isinstance(objectives, list):
                raise ValueError(f"Objectives in domain '{d.get('name')}' must be a list.")
            for obj in objectives:
                if not isinstance(obj, dict):
                    raise ValueError("Objective entry must be a dictionary.")
                why_ids = obj.get("why_ids")
                if why_ids is not None and not isinstance(why_ids, list):
                    raise ValueError(f"Objective '{obj.get('title')}' why_ids must be a list.")
                rel_dom_ids = obj.get("related_domain_ids")
                if rel_dom_ids is not None and not isinstance(rel_dom_ids, list):
                    raise ValueError(
                        f"Objective '{obj.get('title')}' related_domain_ids must be a list."
                    )

            # Validate goals
            goals = d.get("goals", [])
            if not isinstance(goals, list):
                raise ValueError(f"Goals in domain '{d.get('name')}' must be a list.")
            for g in goals:
                if not isinstance(g, dict):
                    raise ValueError("Goal entry must be a dictionary.")
                obj_ids = g.get("objective_ids")
                if obj_ids is not None and not isinstance(obj_ids, list):
                    raise ValueError(f"Goal '{g.get('title')}' objective_ids must be a list.")

        # Validate decisions
        decisions = fw.get("decisions", [])
        if not isinstance(decisions, list):
            raise ValueError(f"Decisions in framework '{fw.get('name')}' must be a list.")
        for dec in decisions:
            if not isinstance(dec, dict):
                raise ValueError("Decision entry must be a dictionary.")
            created_at = dec.get("created_at")
            if created_at is not None and not isinstance(created_at, str):
                raise ValueError(f"Decision '{dec.get('title')}' created_at must be a string.")

        # Validate reflections
        reflections = fw.get("reflections", [])
        if not isinstance(reflections, list):
            raise ValueError(f"Reflections in framework '{fw.get('name')}' must be a list.")
        for ref in reflections:
            if not isinstance(ref, dict):
                raise ValueError("Reflection entry must be a dictionary.")
            created_at = ref.get("created_at")
            if created_at is not None and not isinstance(created_at, str):
                raise ValueError("Reflection log created_at must be a string.")


def restore_user_data_from_dict(user: User, data: dict[str, Any]) -> int:
    """Restores user data from serialized dictionary format."""
    _validate_vault_data(data)
    frameworks_data = data.get("frameworks", [])
    restored_count = 0

    for fw_data in frameworks_data:
        fw = Framework.objects.create(
            owner=user,
            name=fw_data.get("name", "Restored Framework"),
            description=fw_data.get("description", ""),
            is_sample=bool(fw_data.get("is_sample", False)),
        )
        restored_count += 1

        domains_by_id: dict[str, Domain] = {}
        domains_by_name: dict[str, Domain] = {}
        whys_by_id: dict[str, Why] = {}
        whys_by_title: dict[str, Why] = {}
        objectives_by_id: dict[str, Objective] = {}
        objectives_by_title: dict[str, Objective] = {}

        # 1. Create Domains and Whys
        for d_data in fw_data.get("domains", []):
            dom = Domain.objects.create(
                framework=fw,
                name=d_data.get("name", "Domain"),
                description=d_data.get("description", ""),
                display_order=d_data.get("display_order", 0),
            )
            d_export_id = d_data.get("export_id")
            if d_export_id:
                domains_by_id[str(d_export_id)] = dom
            domains_by_name[dom.name] = dom

            for w_data in d_data.get("whys", []):
                why = Why.objects.create(
                    domain=dom,
                    title=w_data.get("title", "Why"),
                    description=w_data.get("description", ""),
                    is_non_negotiable=w_data.get("is_non_negotiable", False),
                    display_order=w_data.get("display_order", 0),
                    last_reviewed_at=w_data.get("last_reviewed_at"),
                )
                w_export_id = w_data.get("export_id")
                if w_export_id:
                    whys_by_id[str(w_export_id)] = why
                whys_by_title[why.title] = why

        # 2. Create Objectives
        for d_data in fw_data.get("domains", []):
            d_export_id = d_data.get("export_id")
            dom = (
                domains_by_id.get(str(d_export_id))
                if d_export_id
                else domains_by_name.get(d_data.get("name", ""))
            )
            if not dom:
                continue
            for o_data in d_data.get("objectives", []):
                obj = Objective.objects.create(
                    primary_domain=dom,
                    title=o_data.get("title", "Objective"),
                    description=o_data.get("description", ""),
                    status=o_data.get("status", StatusChoices.ACTIVE),
                    last_reviewed_at=o_data.get("last_reviewed_at"),
                )
                o_export_id = o_data.get("export_id")
                if o_export_id:
                    objectives_by_id[str(o_export_id)] = obj
                objectives_by_title[obj.title] = obj

                # Rebuild Why links (prefer ID, fallback to title only if no IDs exported)
                linked_whys = []
                explicit_why_ids = o_data.get("why_ids")
                if explicit_why_ids is not None:
                    for wid in explicit_why_ids:
                        if str(wid) in whys_by_id:
                            linked_whys.append(whys_by_id[str(wid)])
                else:
                    for w_title in o_data.get("whys", []):
                        if w_title in whys_by_title:
                            linked_whys.append(whys_by_title[w_title])
                if linked_whys:
                    obj.whys.add(*linked_whys)

                # Rebuild Related Domain links (prefer ID; do NOT fallback to arbitrary
                # name match if explicit IDs were given)
                linked_domains = []
                explicit_dom_ids = o_data.get("related_domain_ids")
                if explicit_dom_ids is not None:
                    for did in explicit_dom_ids:
                        if str(did) in domains_by_id:
                            linked_domains.append(domains_by_id[str(did)])
                else:
                    for rd_name in o_data.get("related_domains", []):
                        if rd_name in domains_by_name:
                            linked_domains.append(domains_by_name[rd_name])
                if linked_domains:
                    obj.related_domains.add(*linked_domains)

        # 3. Create Goals
        for d_data in fw_data.get("domains", []):
            d_export_id = d_data.get("export_id")
            dom = (
                domains_by_id.get(str(d_export_id))
                if d_export_id
                else domains_by_name.get(d_data.get("name", ""))
            )
            if not dom:
                continue
            for g_data in d_data.get("goals", []):
                goal = Goal.objects.create(
                    primary_domain=dom,
                    title=g_data.get("title", "Goal"),
                    description=g_data.get("description", ""),
                    status=g_data.get("status", StatusChoices.ACTIVE),
                    target_date=g_data.get("target_date"),
                    last_reviewed_at=g_data.get("last_reviewed_at"),
                )

                linked_objs = []
                explicit_obj_ids = g_data.get("objective_ids")
                if explicit_obj_ids is not None:
                    for oid in explicit_obj_ids:
                        if str(oid) in objectives_by_id:
                            linked_objs.append(objectives_by_id[str(oid)])
                else:
                    for o_title in g_data.get("objectives", []):
                        if o_title in objectives_by_title:
                            linked_objs.append(objectives_by_title[o_title])
                if linked_objs:
                    goal.objectives.add(*linked_objs)

                linked_rds = []
                explicit_goal_dom_ids = g_data.get("related_domain_ids")
                if explicit_goal_dom_ids is not None:
                    for did in explicit_goal_dom_ids:
                        if str(did) in domains_by_id:
                            linked_rds.append(domains_by_id[str(did)])
                else:
                    for rd_name in g_data.get("related_domains", []):
                        if rd_name in domains_by_name:
                            linked_rds.append(domains_by_name[rd_name])
                if linked_rds:
                    goal.related_domains.add(*linked_rds)

        # 4. Create Decisions
        decisions_by_id: dict[str, DecisionRecord] = {}
        decisions_by_title: dict[str, DecisionRecord] = {}
        for dec_data in fw_data.get("decisions", []):
            dec = DecisionRecord.objects.create(
                framework=fw,
                title=dec_data.get("title", "Decision"),
                proposal_description=dec_data.get("proposal_description", ""),
                benefits_and_costs=dec_data.get("benefits_and_costs", ""),
                alternatives_considered=dec_data.get("alternatives_considered", ""),
                unresolved_questions=dec_data.get("unresolved_questions", ""),
                decision_outcome=dec_data.get("decision_outcome", ""),
                status=dec_data.get("status", "EXPLORING"),
            )
            dec_export_id = dec_data.get("export_id")
            if dec_export_id:
                decisions_by_id[str(dec_export_id)] = dec
            decisions_by_title[dec.title] = dec

            # Restore original decision created_at if present
            raw_dec_created_at = dec_data.get("created_at")
            if raw_dec_created_at:
                dt = parse_datetime(raw_dec_created_at)
                if dt:
                    DecisionRecord.objects.filter(id=dec.id).update(created_at=dt)

            # Rebuild affected domains
            aff_domains = []
            explicit_aff_dom_ids = dec_data.get("affected_domain_ids")
            if explicit_aff_dom_ids is not None:
                for did in explicit_aff_dom_ids:
                    if str(did) in domains_by_id:
                        aff_domains.append(domains_by_id[str(did)])
            else:
                for ad_name in dec_data.get("affected_domains", []):
                    if ad_name in domains_by_name:
                        aff_domains.append(domains_by_name[ad_name])
            if aff_domains:
                dec.affected_domains.add(*aff_domains)

            # Rebuild relevant whys
            rel_whys = []
            explicit_rel_why_ids = dec_data.get("relevant_why_ids")
            if explicit_rel_why_ids is not None:
                for wid in explicit_rel_why_ids:
                    if str(wid) in whys_by_id:
                        rel_whys.append(whys_by_id[str(wid)])
            else:
                for rw_title in dec_data.get("relevant_whys", []):
                    if rw_title in whys_by_title:
                        rel_whys.append(whys_by_title[rw_title])
            if rel_whys:
                dec.relevant_whys.add(*rel_whys)

            # Rebuild supporting objectives
            supp_objs = []
            explicit_supp_obj_ids = dec_data.get("supporting_objective_ids")
            if explicit_supp_obj_ids is not None:
                for oid in explicit_supp_obj_ids:
                    if str(oid) in objectives_by_id:
                        supp_objs.append(objectives_by_id[str(oid)])
            else:
                for so_title in dec_data.get("supporting_objectives", []):
                    if so_title in objectives_by_title:
                        supp_objs.append(objectives_by_title[so_title])
            if supp_objs:
                dec.supporting_objectives.add(*supp_objs)

            # Rebuild conflicting objectives
            conf_objs = []
            explicit_conf_obj_ids = dec_data.get("conflicting_objective_ids")
            if explicit_conf_obj_ids is not None:
                for oid in explicit_conf_obj_ids:
                    if str(oid) in objectives_by_id:
                        conf_objs.append(objectives_by_id[str(oid)])
            else:
                for co_title in dec_data.get("conflicting_objectives", []):
                    if co_title in objectives_by_title:
                        conf_objs.append(objectives_by_title[co_title])
            if conf_objs:
                dec.conflicting_objectives.add(*conf_objs)

        # 5. Create Reflections
        for ref_data in fw_data.get("reflections", []):
            parent_dec = None
            if ref_data.get("decision_id"):
                parent_dec = decisions_by_id.get(str(ref_data["decision_id"]))
            if not parent_dec and ref_data.get("decision_title"):
                parent_dec = decisions_by_title.get(ref_data["decision_title"])

            ref_log = LLMReflectionLog.objects.create(
                framework=fw,
                decision=parent_dec,
                user_prompt=ref_data.get("user_prompt", ""),
                context_snapshot=ref_data.get("context_snapshot", ""),
                llm_response=ref_data.get("llm_response", ""),
                provider_used=ref_data.get("provider_used", "Unknown"),
            )
            exported_created_at = ref_data.get("created_at")
            if exported_created_at:
                dt = parse_datetime(exported_created_at)
                if dt:
                    LLMReflectionLog.objects.filter(id=ref_log.id).update(created_at=dt)

    return restored_count


def decrypt_and_restore_vault(
    user: User, vault_envelope: dict[str, Any], password: str
) -> int:
    """Decrypts a vault envelope using the supplied password and restores data."""
    salt_b64 = vault_envelope.get("salt")
    ciphertext = vault_envelope.get("ciphertext")
    if not salt_b64 or not ciphertext:
        raise ValueError("Invalid vault envelope: missing salt or ciphertext.")

    iterations = vault_envelope.get("iterations", DEFAULT_PBKDF2_ITERATIONS)
    if not isinstance(iterations, int) or iterations not in ALLOWED_PBKDF2_ITERATIONS:
        raise ValueError(
            f"Unsupported or unauthorized PBKDF2 iteration count in vault envelope: {iterations}"
        )

    salt = base64.b64decode(salt_b64.encode("utf-8"))
    key = derive_vault_key(password, salt, iterations=iterations)
    cipher = Fernet(key)

    try:
        raw_json = cipher.decrypt(ciphertext.encode("utf-8"))
        if len(raw_json) > MAX_RAW_VAULT_BYTES:
            raise ValueError("Decrypted vault contents exceed maximum allowed size.")
        data = json.loads(raw_json.decode("utf-8"))
    except InvalidToken as err:
        raise ValueError("Invalid vault password. Decryption failed.") from err
    except ValueError:
        raise
    except Exception as err:
        raise ValueError(f"Vault data corrupted or invalid format: {err}") from err

    with transaction.atomic():
        return restore_user_data_from_dict(user, data)
