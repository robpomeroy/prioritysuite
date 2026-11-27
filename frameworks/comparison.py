from typing import Any


def serialize_framework_for_snapshot(framework) -> dict[str, Any]:
    """Generates a canonical serialized dictionary of a single framework."""
    domains_list = []
    for d in framework.domains.all():
        whys_list = [
            {
                "id": w.id,
                "title": w.title,
                "description": w.description,
                "is_non_negotiable": w.is_non_negotiable,
                "is_sample": w.is_sample,
            }
            for w in d.whys.all()
        ]

        objectives_list = [
            {
                "id": obj.id,
                "title": obj.title,
                "description": obj.description,
                "status": obj.status,
                "is_sample": obj.is_sample,
                "whys": [w.title for w in obj.whys.all()],
                "related_domains": [rd.name for rd in obj.related_domains.all()],
            }
            for obj in d.primary_objectives.all()
        ]

        goals_list = [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "status": g.status,
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "is_sample": g.is_sample,
                "objectives": [o.title for o in g.objectives.all()],
                "related_domains": [rd.name for rd in g.related_domains.all()],
            }
            for g in d.primary_goals.all()
        ]

        domains_list.append(
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "whys": whys_list,
                "objectives": objectives_list,
                "goals": goals_list,
            }
        )

    decisions_list = [
        {
            "id": dec.id,
            "title": dec.title,
            "proposal_description": dec.proposal_description,
            "status": dec.status,
            "decision_outcome": dec.decision_outcome,
        }
        for dec in framework.decisions.all()
    ]

    return {
        "id": framework.id,
        "name": framework.name,
        "description": framework.description,
        "domains": domains_list,
        "decisions": decisions_list,
    }


def _match_records_and_diff(
    snap_items: list[dict[str, Any]],
    live_items: list[dict[str, Any]],
    name_or_title_key: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[tuple[dict[str, Any], dict[str, Any]]],
]:
    """
    Matches records between snapshot and live state by stable id if available,
    or falls back to title/name matching with support for duplicate titles.
    Returns: (added_items, removed_items, matched_pairs)
    """
    live_by_id = {}
    snap_by_id = {}
    live_unmatched = []
    snap_unmatched = []

    for item in live_items:
        iid = item.get("id")
        if iid is not None:
            live_by_id[str(iid)] = item
        else:
            live_unmatched.append(item)

    for item in snap_items:
        iid = item.get("id")
        if iid is not None:
            snap_by_id[str(iid)] = item
        else:
            snap_unmatched.append(item)

    matched_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    matched_snap_ids = set()
    matched_live_ids = set()

    # Match by ID first
    for iid, s_item in snap_by_id.items():
        if iid in live_by_id:
            matched_pairs.append((s_item, live_by_id[iid]))
            matched_snap_ids.add(iid)
            matched_live_ids.add(iid)

    # Remaining items with unmatched IDs
    rem_live = [
        item for iid, item in live_by_id.items() if iid not in matched_live_ids
    ] + live_unmatched
    rem_snap = [
        item for iid, item in snap_by_id.items() if iid not in matched_snap_ids
    ] + snap_unmatched

    # Match remaining by title/name (consuming one-to-one to handle duplicates)
    unmatched_live: list[dict[str, Any]] = []
    for l_item in rem_live:
        target_val = l_item.get(name_or_title_key)
        found_idx = None
        for idx, s_item in enumerate(rem_snap):
            if s_item.get(name_or_title_key) == target_val:
                found_idx = idx
                break
        if found_idx is not None:
            matched_pairs.append((rem_snap.pop(found_idx), l_item))
        else:
            unmatched_live.append(l_item)

    return unmatched_live, rem_snap, matched_pairs


def compare_framework_states(
    snapshot_state: dict[str, Any], live_state: dict[str, Any]
) -> dict[str, Any]:
    """
    Compares a historical snapshot dictionary against the live framework dictionary.
    Returns categorized lists:
    - added_items
    - removed_items
    - status_changes
    - unchanged_counts
    """
    diff: dict[str, list[dict[str, Any]]] = {
        "added_domains": [],
        "removed_domains": [],
        "modified_domains": [],
        "added_whys": [],
        "removed_whys": [],
        "modified_whys": [],
        "added_objectives": [],
        "removed_objectives": [],
        "status_changed_objectives": [],
        "modified_objectives": [],
        "added_goals": [],
        "removed_goals": [],
        "status_changed_goals": [],
        "modified_goals": [],
        "added_decisions": [],
        "removed_decisions": [],
        "status_changed_decisions": [],
        "modified_decisions": [],
    }

    # Domains
    snap_domains = snapshot_state.get("domains", []) or []
    live_domains = live_state.get("domains", []) or []
    add_doms, rem_doms, matched_doms = _match_records_and_diff(
        snap_domains, live_domains, "name"
    )
    for d in add_doms:
        diff["added_domains"].append({"name": d.get("name")})
    for d in rem_doms:
        diff["removed_domains"].append({"name": d.get("name")})
    for s_dom, l_dom in matched_doms:
        if (
            s_dom.get("name") != l_dom.get("name")
            or (s_dom.get("description") or "") != (l_dom.get("description") or "")
        ):
            diff["modified_domains"].append({"name": l_dom.get("name")})

    # Whys
    snap_whys = [w for d in snap_domains for w in (d.get("whys") or [])]
    live_whys = [w for d in live_domains for w in (d.get("whys") or [])]
    add_whys, rem_whys, matched_whys = _match_records_and_diff(
        snap_whys, live_whys, "title"
    )
    for w in add_whys:
        diff["added_whys"].append({"title": w.get("title")})
    for w in rem_whys:
        diff["removed_whys"].append({"title": w.get("title")})
    for s_why, l_why in matched_whys:
        if (
            s_why.get("title") != l_why.get("title")
            or (s_why.get("description") or "") != (l_why.get("description") or "")
            or s_why.get("is_non_negotiable") != l_why.get("is_non_negotiable")
        ):
            diff["modified_whys"].append({"title": l_why.get("title")})

    # Objectives
    snap_objs = [obj for d in snap_domains for obj in (d.get("objectives") or [])]
    live_objs = [obj for d in live_domains for obj in (d.get("objectives") or [])]
    add_objs, rem_objs, matched_objs = _match_records_and_diff(
        snap_objs, live_objs, "title"
    )
    for obj in add_objs:
        diff["added_objectives"].append(
            {"title": obj.get("title"), "status": obj.get("status")}
        )
    for obj in rem_objs:
        diff["removed_objectives"].append(
            {"title": obj.get("title"), "status": obj.get("status")}
        )
    for s_obj, l_obj in matched_objs:
        if s_obj.get("status") != l_obj.get("status"):
            diff["status_changed_objectives"].append(
                {
                    "title": l_obj.get("title"),
                    "old_status": s_obj.get("status"),
                    "new_status": l_obj.get("status"),
                }
            )
        if (
            s_obj.get("title") != l_obj.get("title")
            or (s_obj.get("description") or "") != (l_obj.get("description") or "")
            or set(s_obj.get("whys") or []) != set(l_obj.get("whys") or [])
            or set(s_obj.get("related_domains") or [])
            != set(l_obj.get("related_domains") or [])
        ):
            diff["modified_objectives"].append({"title": l_obj.get("title")})

    # Goals
    snap_goals = [g for d in snap_domains for g in (d.get("goals") or [])]
    live_goals = [g for d in live_domains for g in (d.get("goals") or [])]
    add_goals, rem_goals, matched_goals = _match_records_and_diff(
        snap_goals, live_goals, "title"
    )
    for g in add_goals:
        diff["added_goals"].append(
            {"title": g.get("title"), "status": g.get("status")}
        )
    for g in rem_goals:
        diff["removed_goals"].append(
            {"title": g.get("title"), "status": g.get("status")}
        )
    for s_g, l_g in matched_goals:
        if s_g.get("status") != l_g.get("status"):
            diff["status_changed_goals"].append(
                {
                    "title": l_g.get("title"),
                    "old_status": s_g.get("status"),
                    "new_status": l_g.get("status"),
                }
            )
        if (
            s_g.get("title") != l_g.get("title")
            or (s_g.get("description") or "") != (l_g.get("description") or "")
            or s_g.get("target_date") != l_g.get("target_date")
            or set(s_g.get("objectives") or []) != set(l_g.get("objectives") or [])
            or set(s_g.get("related_domains") or [])
            != set(l_g.get("related_domains") or [])
        ):
            diff["modified_goals"].append({"title": l_g.get("title")})

    # Decisions
    snap_decs = snapshot_state.get("decisions", []) or []
    live_decs = live_state.get("decisions", []) or []
    add_decs, rem_decs, matched_decs = _match_records_and_diff(
        snap_decs, live_decs, "title"
    )
    for dec in add_decs:
        diff["added_decisions"].append(
            {"title": dec.get("title"), "status": dec.get("status")}
        )
    for dec in rem_decs:
        diff["removed_decisions"].append(
            {"title": dec.get("title"), "status": dec.get("status")}
        )
    for s_dec, l_dec in matched_decs:
        if s_dec.get("status") != l_dec.get("status"):
            diff["status_changed_decisions"].append(
                {
                    "title": l_dec.get("title"),
                    "old_status": s_dec.get("status"),
                    "new_status": l_dec.get("status"),
                }
            )
        if (
            s_dec.get("title") != l_dec.get("title")
            or (s_dec.get("proposal_description") or "")
            != (l_dec.get("proposal_description") or "")
            or (s_dec.get("decision_outcome") or "")
            != (l_dec.get("decision_outcome") or "")
        ):
            diff["modified_decisions"].append({"title": l_dec.get("title")})

    return diff
