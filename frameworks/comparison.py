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
        "added_whys": [],
        "removed_whys": [],
        "added_objectives": [],
        "removed_objectives": [],
        "status_changed_objectives": [],
        "added_goals": [],
        "removed_goals": [],
        "status_changed_goals": [],
        "added_decisions": [],
        "removed_decisions": [],
    }

    # Domains
    snap_dom_names = {d["name"]: d for d in snapshot_state.get("domains", [])}
    live_dom_names = {d["name"]: d for d in live_state.get("domains", [])}

    for name in live_dom_names:
        if name not in snap_dom_names:
            diff["added_domains"].append({"name": name})

    for name in snap_dom_names:
        if name not in live_dom_names:
            diff["removed_domains"].append({"name": name})

    # Whys
    snap_whys = {
        w["title"]: w
        for d in snapshot_state.get("domains", [])
        for w in d.get("whys", [])
    }
    live_whys = {
        w["title"]: w
        for d in live_state.get("domains", [])
        for w in d.get("whys", [])
    }

    for title, _w in live_whys.items():
        if title not in snap_whys:
            diff["added_whys"].append({"title": title})

    for title, _w in snap_whys.items():
        if title not in live_whys:
            diff["removed_whys"].append({"title": title})

    # Objectives
    snap_objs = {
        obj["title"]: obj
        for d in snapshot_state.get("domains", [])
        for obj in d.get("objectives", [])
    }
    live_objs = {
        obj["title"]: obj
        for d in live_state.get("domains", [])
        for obj in d.get("objectives", [])
    }

    for title, obj in live_objs.items():
        if title not in snap_objs:
            diff["added_objectives"].append({"title": title, "status": obj.get("status")})
        elif obj.get("status") != snap_objs[title].get("status"):
            diff["status_changed_objectives"].append(
                {
                    "title": title,
                    "old_status": snap_objs[title].get("status"),
                    "new_status": obj.get("status"),
                }
            )

    for title, obj in snap_objs.items():
        if title not in live_objs:
            diff["removed_objectives"].append({"title": title, "status": obj.get("status")})

    # Goals
    snap_goals = {
        g["title"]: g
        for d in snapshot_state.get("domains", [])
        for g in d.get("goals", [])
    }
    live_goals = {
        g["title"]: g
        for d in live_state.get("domains", [])
        for g in d.get("goals", [])
    }

    for title, g in live_goals.items():
        if title not in snap_goals:
            diff["added_goals"].append({"title": title, "status": g.get("status")})
        elif g.get("status") != snap_goals[title].get("status"):
            diff["status_changed_goals"].append(
                {
                    "title": title,
                    "old_status": snap_goals[title].get("status"),
                    "new_status": g.get("status"),
                }
            )

    for title, g in snap_goals.items():
        if title not in live_goals:
            diff["removed_goals"].append({"title": title, "status": g.get("status")})

    # Decisions
    snap_decs = {dec["title"]: dec for dec in snapshot_state.get("decisions", [])}
    live_decs = {dec["title"]: dec for dec in live_state.get("decisions", [])}

    for title, dec in live_decs.items():
        if title not in snap_decs:
            diff["added_decisions"].append({"title": title, "status": dec.get("status")})

    for title, dec in snap_decs.items():
        if title not in live_decs:
            diff["removed_decisions"].append({"title": title, "status": dec.get("status")})

    return diff
