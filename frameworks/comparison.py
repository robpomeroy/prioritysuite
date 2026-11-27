from typing import Any


def serialize_framework_for_snapshot(framework) -> dict[str, Any]:
    """
    Generates a canonical serialized dictionary of a single framework.
    Uses prefetch_related to guarantee constant query execution count.
    """
    domains = list(
        framework.domains.prefetch_related(
            "whys",
            "primary_objectives__whys",
            "primary_objectives__related_domains",
            "primary_goals__objectives",
            "primary_goals__related_domains",
        ).all()
    )

    domains_list = []
    for d in domains:
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

    decisions = list(
        framework.decisions.prefetch_related(
            "affected_domains",
            "relevant_whys",
            "supporting_objectives",
            "conflicting_objectives",
        ).all()
    )

    decisions_list = [
        {
            "id": dec.id,
            "title": dec.title,
            "proposal_description": dec.proposal_description,
            "benefits_and_costs": dec.benefits_and_costs,
            "alternatives_considered": dec.alternatives_considered,
            "unresolved_questions": dec.unresolved_questions,
            "decision_outcome": dec.decision_outcome,
            "status": dec.status,
            "affected_domains": [ad.name for ad in dec.affected_domains.all()],
            "relevant_whys": [rw.title for rw in dec.relevant_whys.all()],
            "supporting_objectives": [
                so.title for so in dec.supporting_objectives.all()
            ],
            "conflicting_objectives": [
                co.title for co in dec.conflicting_objectives.all()
            ],
        }
        for dec in decisions
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
    Defensively ignores non-dict items.
    Returns: (added_items, removed_items, matched_pairs)
    """
    clean_live = [item for item in live_items if isinstance(item, dict)]
    clean_snap = [item for item in snap_items if isinstance(item, dict)]

    live_by_id = {}
    snap_by_id = {}
    live_unmatched = []
    snap_unmatched = []

    for item in clean_live:
        iid = item.get("id")
        if iid is not None:
            live_by_id[str(iid)] = item
        else:
            live_unmatched.append(item)

    for item in clean_snap:
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


def _safe_str_list(val: Any) -> list[str]:
    """Coerces an arbitrary value safely into a list of strings."""
    if not isinstance(val, (list, tuple, set)):
        return []
    return [str(x) for x in val if x is not None]


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

    if not isinstance(snapshot_state, dict) or not isinstance(live_state, dict):
        return diff

    # Domains
    raw_snap_domains = snapshot_state.get("domains")
    raw_live_domains = live_state.get("domains")
    snap_domains = (
        [d for d in raw_snap_domains if isinstance(d, dict)]
        if isinstance(raw_snap_domains, list)
        else []
    )
    live_domains = (
        [d for d in raw_live_domains if isinstance(d, dict)]
        if isinstance(raw_live_domains, list)
        else []
    )

    add_doms, rem_doms, matched_doms = _match_records_and_diff(
        snap_domains, live_domains, "name"
    )
    for d in add_doms:
        diff["added_domains"].append({"name": d.get("name")})
    for d in rem_doms:
        diff["removed_domains"].append({"name": d.get("name")})
    for s_dom, l_dom in matched_doms:
        name_changed = s_dom.get("name") != l_dom.get("name")
        desc_changed = (s_dom.get("description") or "") != (
            l_dom.get("description") or ""
        )
        if name_changed or desc_changed:
            entry: dict[str, Any] = {"name": l_dom.get("name")}
            if name_changed:
                entry["old_name"] = s_dom.get("name")
            diff["modified_domains"].append(entry)

    # Whys (track parent domain to detect reassignments)
    def _extract_whys(domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        whys = []
        for d in domains:
            d_name = d.get("name") or "Unnamed Domain"
            d_id = d.get("id")
            raw_whys = d.get("whys")
            if isinstance(raw_whys, list):
                for w in raw_whys:
                    if isinstance(w, dict):
                        w_copy = dict(w)
                        w_copy["domain"] = d_name
                        w_copy["domain_id"] = d_id
                        whys.append(w_copy)
        return whys

    snap_whys = _extract_whys(snap_domains)
    live_whys = _extract_whys(live_domains)
    add_whys, rem_whys, matched_whys = _match_records_and_diff(
        snap_whys, live_whys, "title"
    )
    for w in add_whys:
        diff["added_whys"].append({"title": w.get("title")})
    for w in rem_whys:
        diff["removed_whys"].append({"title": w.get("title")})
    for s_why, l_why in matched_whys:
        title_changed = s_why.get("title") != l_why.get("title")
        desc_changed = (s_why.get("description") or "") != (
            l_why.get("description") or ""
        )
        non_neg_changed = s_why.get("is_non_negotiable") != l_why.get(
            "is_non_negotiable"
        )
        s_dom_id = s_why.get("domain_id")
        l_dom_id = l_why.get("domain_id")
        if s_dom_id is not None and l_dom_id is not None:
            domain_changed = str(s_dom_id) != str(l_dom_id)
        else:
            domain_changed = s_why.get("domain") != l_why.get("domain")
        if title_changed or desc_changed or non_neg_changed or domain_changed:
            entry = {"title": l_why.get("title")}
            if title_changed:
                entry["old_title"] = s_why.get("title")
            if domain_changed:
                entry["old_domain"] = s_why.get("domain")
                entry["new_domain"] = l_why.get("domain")
            diff["modified_whys"].append(entry)

    # Objectives (track parent domain to detect reassignments)
    def _extract_objectives(
        domains: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        objs = []
        for d in domains:
            d_name = d.get("name") or "Unnamed Domain"
            d_id = d.get("id")
            raw_objs = d.get("objectives")
            if isinstance(raw_objs, list):
                for obj in raw_objs:
                    if isinstance(obj, dict):
                        obj_copy = dict(obj)
                        obj_copy["domain"] = d_name
                        obj_copy["domain_id"] = d_id
                        objs.append(obj_copy)
        return objs

    snap_objs = _extract_objectives(snap_domains)
    live_objs = _extract_objectives(live_domains)
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
        title_changed = s_obj.get("title") != l_obj.get("title")
        desc_changed = (s_obj.get("description") or "") != (
            l_obj.get("description") or ""
        )
        whys_changed = set(_safe_str_list(s_obj.get("whys"))) != set(
            _safe_str_list(l_obj.get("whys"))
        )
        rd_changed = set(
            _safe_str_list(s_obj.get("related_domains"))
        ) != set(_safe_str_list(l_obj.get("related_domains")))
        s_dom_id = s_obj.get("domain_id")
        l_dom_id = l_obj.get("domain_id")
        if s_dom_id is not None and l_dom_id is not None:
            domain_changed = str(s_dom_id) != str(l_dom_id)
        else:
            domain_changed = s_obj.get("domain") != l_obj.get("domain")
        if (
            title_changed
            or desc_changed
            or whys_changed
            or rd_changed
            or domain_changed
        ):
            entry = {"title": l_obj.get("title")}
            if title_changed:
                entry["old_title"] = s_obj.get("title")
            if domain_changed:
                entry["old_domain"] = s_obj.get("domain")
                entry["new_domain"] = l_obj.get("domain")
            diff["modified_objectives"].append(entry)

    # Goals (track parent domain to detect reassignments)
    def _extract_goals(domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        goals = []
        for d in domains:
            d_name = d.get("name") or "Unnamed Domain"
            d_id = d.get("id")
            raw_goals = d.get("goals")
            if isinstance(raw_goals, list):
                for g in raw_goals:
                    if isinstance(g, dict):
                        g_copy = dict(g)
                        g_copy["domain"] = d_name
                        g_copy["domain_id"] = d_id
                        goals.append(g_copy)
        return goals

    snap_goals = _extract_goals(snap_domains)
    live_goals = _extract_goals(live_domains)
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
        title_changed = s_g.get("title") != l_g.get("title")
        desc_changed = (s_g.get("description") or "") != (
            l_g.get("description") or ""
        )
        target_date_changed = s_g.get("target_date") != l_g.get("target_date")
        objs_changed = set(_safe_str_list(s_g.get("objectives"))) != set(
            _safe_str_list(l_g.get("objectives"))
        )
        rd_changed = set(
            _safe_str_list(s_g.get("related_domains"))
        ) != set(_safe_str_list(l_g.get("related_domains")))
        s_dom_id = s_g.get("domain_id")
        l_dom_id = l_g.get("domain_id")
        if s_dom_id is not None and l_dom_id is not None:
            domain_changed = str(s_dom_id) != str(l_dom_id)
        else:
            domain_changed = s_g.get("domain") != l_g.get("domain")
        if (
            title_changed
            or desc_changed
            or target_date_changed
            or objs_changed
            or rd_changed
            or domain_changed
        ):
            entry = {"title": l_g.get("title")}
            if title_changed:
                entry["old_title"] = s_g.get("title")
            if domain_changed:
                entry["old_domain"] = s_g.get("domain")
                entry["new_domain"] = l_g.get("domain")
            diff["modified_goals"].append(entry)

    # Decisions
    raw_snap_decs = snapshot_state.get("decisions")
    raw_live_decs = live_state.get("decisions")
    snap_decs = (
        [d for d in raw_snap_decs if isinstance(d, dict)]
        if isinstance(raw_snap_decs, list)
        else []
    )
    live_decs = (
        [d for d in raw_live_decs if isinstance(d, dict)]
        if isinstance(raw_live_decs, list)
        else []
    )

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
        title_changed = s_dec.get("title") != l_dec.get("title")
        desc_changed = (s_dec.get("proposal_description") or "") != (
            l_dec.get("proposal_description") or ""
        )
        outcome_changed = (s_dec.get("decision_outcome") or "") != (
            l_dec.get("decision_outcome") or ""
        )
        benefits_changed = (s_dec.get("benefits_and_costs") or "") != (
            l_dec.get("benefits_and_costs") or ""
        )
        alts_changed = (s_dec.get("alternatives_considered") or "") != (
            l_dec.get("alternatives_considered") or ""
        )
        unres_changed = (s_dec.get("unresolved_questions") or "") != (
            l_dec.get("unresolved_questions") or ""
        )
        aff_doms_changed = set(
            _safe_str_list(s_dec.get("affected_domains"))
        ) != set(_safe_str_list(l_dec.get("affected_domains")))
        rel_whys_changed = set(
            _safe_str_list(s_dec.get("relevant_whys"))
        ) != set(_safe_str_list(l_dec.get("relevant_whys")))
        supp_objs_changed = set(
            _safe_str_list(s_dec.get("supporting_objectives"))
        ) != set(_safe_str_list(l_dec.get("supporting_objectives")))
        conf_objs_changed = set(
            _safe_str_list(s_dec.get("conflicting_objectives"))
        ) != set(_safe_str_list(l_dec.get("conflicting_objectives")))

        if (
            title_changed
            or desc_changed
            or outcome_changed
            or benefits_changed
            or alts_changed
            or unres_changed
            or aff_doms_changed
            or rel_whys_changed
            or supp_objs_changed
            or conf_objs_changed
        ):
            entry = {"title": l_dec.get("title")}
            if title_changed:
                entry["old_title"] = s_dec.get("title")
            diff["modified_decisions"].append(entry)

    return diff
