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

from decisions.models import DecisionRecord, LLMReflectionLog
from frameworks.models import Domain, Framework, Goal, Objective, StatusChoices, Why

logger = logging.getLogger(__name__)


def derive_vault_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte url-safe base64 key from password and salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def serialize_user_data(user: User) -> dict[str, Any]:
    """Serializes all private frameworks, domains, whys, objectives, goals,

    decisions, and reflection logs for the given user.
    """
    frameworks_data = []
    for fw in Framework.objects.filter(owner=user).prefetch_related(
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
    ):
        domains_list = []

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
                objectives_list.append(
                    {
                        "export_id": str(obj.id),
                        "title": obj.title,
                        "description": obj.description,
                        "status": obj.status,
                        "whys": [w.title for w in obj.whys.all()],
                        "why_ids": [str(w.id) for w in obj.whys.all()],
                        "related_domains": [rd.name for rd in obj.related_domains.all()],
                        "related_domain_ids": [str(rd.id) for rd in obj.related_domains.all()],
                        "last_reviewed_at": (
                            obj.last_reviewed_at.isoformat() if obj.last_reviewed_at else None
                        ),
                    }
                )

            goals_list = []
            for g in d.primary_goals.all():
                goals_list.append(
                    {
                        "export_id": str(g.id),
                        "title": g.title,
                        "description": g.description,
                        "status": g.status,
                        "target_date": g.target_date.isoformat() if g.target_date else None,
                        "objectives": [o.title for o in g.objectives.all()],
                        "objective_ids": [str(o.id) for o in g.objectives.all()],
                        "related_domains": [rd.name for rd in g.related_domains.all()],
                        "related_domain_ids": [str(rd.id) for rd in g.related_domains.all()],
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
                    "affected_domains": [ad.name for ad in dec.affected_domains.all()],
                    "affected_domain_ids": [str(ad.id) for ad in dec.affected_domains.all()],
                    "relevant_whys": [rw.title for rw in dec.relevant_whys.all()],
                    "relevant_why_ids": [str(rw.id) for rw in dec.relevant_whys.all()],
                    "supporting_objectives": [so.title for so in dec.supporting_objectives.all()],
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
    key = derive_vault_key(password, salt)
    cipher = Fernet(key)

    data = serialize_user_data(user)
    raw_json = json.dumps(data, indent=2).encode("utf-8")
    ciphertext = cipher.encrypt(raw_json).decode("utf-8")

    return {
        "format": "prioritysuite-encrypted-vault-v1",
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": 100_000,
        "salt": base64.b64encode(salt).decode("utf-8"),
        "ciphertext": ciphertext,
    }


def restore_user_data_from_dict(user: User, data: dict[str, Any]) -> int:
    """Restores user data from serialized dictionary format."""
    frameworks_data = data.get("frameworks", [])
    restored_count = 0

    for fw_data in frameworks_data:
        fw = Framework.objects.create(
            owner=user,
            name=fw_data.get("name", "Restored Framework"),
            description=fw_data.get("description", ""),
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

                # Rebuild Why links (prefer ID, fallback to title)
                linked_whys = []
                for wid in o_data.get("why_ids", []):
                    if str(wid) in whys_by_id:
                        linked_whys.append(whys_by_id[str(wid)])
                if not linked_whys:
                    for w_title in o_data.get("whys", []):
                        if w_title in whys_by_title:
                            linked_whys.append(whys_by_title[w_title])
                if linked_whys:
                    obj.whys.add(*linked_whys)

                # Rebuild Related Domain links (prefer ID, fallback to name)
                linked_domains = []
                for did in o_data.get("related_domain_ids", []):
                    if str(did) in domains_by_id:
                        linked_domains.append(domains_by_id[str(did)])
                if not linked_domains:
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
                for oid in g_data.get("objective_ids", []):
                    if str(oid) in objectives_by_id:
                        linked_objs.append(objectives_by_id[str(oid)])
                if not linked_objs:
                    for o_title in g_data.get("objectives", []):
                        if o_title in objectives_by_title:
                            linked_objs.append(objectives_by_title[o_title])
                if linked_objs:
                    goal.objectives.add(*linked_objs)

                linked_rds = []
                for did in g_data.get("related_domain_ids", []):
                    if str(did) in domains_by_id:
                        linked_rds.append(domains_by_id[str(did)])
                if not linked_rds:
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

            # Rebuild affected domains
            aff_domains = []
            for did in dec_data.get("affected_domain_ids", []):
                if str(did) in domains_by_id:
                    aff_domains.append(domains_by_id[str(did)])
            if not aff_domains:
                for ad_name in dec_data.get("affected_domains", []):
                    if ad_name in domains_by_name:
                        aff_domains.append(domains_by_name[ad_name])
            if aff_domains:
                dec.affected_domains.add(*aff_domains)

            # Rebuild relevant whys
            rel_whys = []
            for wid in dec_data.get("relevant_why_ids", []):
                if str(wid) in whys_by_id:
                    rel_whys.append(whys_by_id[str(wid)])
            if not rel_whys:
                for rw_title in dec_data.get("relevant_whys", []):
                    if rw_title in whys_by_title:
                        rel_whys.append(whys_by_title[rw_title])
            if rel_whys:
                dec.relevant_whys.add(*rel_whys)

            # Rebuild supporting objectives
            supp_objs = []
            for oid in dec_data.get("supporting_objective_ids", []):
                if str(oid) in objectives_by_id:
                    supp_objs.append(objectives_by_id[str(oid)])
            if not supp_objs:
                for so_title in dec_data.get("supporting_objectives", []):
                    if so_title in objectives_by_title:
                        supp_objs.append(objectives_by_title[so_title])
            if supp_objs:
                dec.supporting_objectives.add(*supp_objs)

            # Rebuild conflicting objectives
            conf_objs = []
            for oid in dec_data.get("conflicting_objective_ids", []):
                if str(oid) in objectives_by_id:
                    conf_objs.append(objectives_by_id[str(oid)])
            if not conf_objs:
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
                from django.utils.dateparse import parse_datetime

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

    salt = base64.b64decode(salt_b64.encode("utf-8"))
    key = derive_vault_key(password, salt)
    cipher = Fernet(key)

    try:
        raw_json = cipher.decrypt(ciphertext.encode("utf-8"))
        data = json.loads(raw_json.decode("utf-8"))
    except InvalidToken as err:
        raise ValueError("Invalid vault password. Decryption failed.") from err
    except Exception as err:
        raise ValueError(f"Vault data corrupted or invalid format: {err}") from err

    with transaction.atomic():
        return restore_user_data_from_dict(user, data)
