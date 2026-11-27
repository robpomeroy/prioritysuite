from typing import Any

from frameworks.models import Framework, StatusChoices


def build_framework_graph(framework: Framework) -> dict[str, Any]:
    """
    Constructs a graph structure representing the 4-tier hierarchy:
    Domain -> Why -> Objective -> Goal, plus cross-domain bridges and
    active decision tension overlays.
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

    domain_ids = {d.id for d in domains}
    decisions = list(
        framework.decisions.prefetch_related(
            "affected_domains",
            "relevant_whys",
            "supporting_objectives",
            "conflicting_objectives",
        ).all()
    )

    nodes = []
    edges = []

    # Diagnostics trackers
    unexpressed_whys = []
    unanchored_goals = []
    cross_domain_items = []
    all_whys_with_objectives = set()

    for d in domains:
        nodes.append(
            {
                "id": f"d_{d.id}",
                "type": "domain",
                "label": d.name,
                "display_order": d.display_order,
                "is_sample": d.is_sample,
            }
        )

        for w in d.whys.all():
            nodes.append(
                {
                    "id": f"w_{w.id}",
                    "type": "why",
                    "label": w.title,
                    "domain_id": d.id,
                    "domain_name": d.name,
                    "is_non_negotiable": w.is_non_negotiable,
                    "is_sample": w.is_sample,
                }
            )
            edges.append(
                {
                    "source": f"d_{d.id}",
                    "target": f"w_{w.id}",
                    "kind": "hierarchy",
                }
            )

        for obj in d.primary_objectives.all():
            nodes.append(
                {
                    "id": f"obj_{obj.id}",
                    "type": "objective",
                    "label": obj.title,
                    "domain_id": d.id,
                    "domain_name": d.name,
                    "status": obj.status,
                    "is_sample": obj.is_sample,
                }
            )
            edges.append(
                {
                    "source": f"d_{d.id}",
                    "target": f"obj_{obj.id}",
                    "kind": "hierarchy",
                }
            )

            linked_whys = list(obj.whys.all())
            for w in linked_whys:
                if obj.status == StatusChoices.ACTIVE:
                    all_whys_with_objectives.add(w.id)
                edges.append(
                    {
                        "source": f"w_{w.id}",
                        "target": f"obj_{obj.id}",
                        "kind": "serves",
                    }
                )

            rel_doms = [
                rd for rd in obj.related_domains.all() if rd.id in domain_ids and rd.id != d.id
            ]
            if rel_doms:
                cross_domain_items.append(
                    {
                        "item_type": "Objective",
                        "title": obj.title,
                        "primary": d.name,
                        "related": [rd.name for rd in rel_doms],
                    }
                )
                for rd in rel_doms:
                    edges.append(
                        {
                            "source": f"obj_{obj.id}",
                            "target": f"d_{rd.id}",
                            "kind": "cross_domain",
                        }
                    )

        for g in d.primary_goals.all():
            nodes.append(
                {
                    "id": f"g_{g.id}",
                    "type": "goal",
                    "label": g.title,
                    "domain_id": d.id,
                    "domain_name": d.name,
                    "status": g.status,
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                    "is_sample": g.is_sample,
                }
            )
            edges.append(
                {
                    "source": f"d_{d.id}",
                    "target": f"g_{g.id}",
                    "kind": "hierarchy",
                }
            )

            linked_objs = list(g.objectives.all())
            if not linked_objs:
                unanchored_goals.append(
                    {
                        "id": g.id,
                        "title": g.title,
                        "domain_name": d.name,
                    }
                )
            else:
                for obj in linked_objs:
                    edges.append(
                        {
                            "source": f"obj_{obj.id}",
                            "target": f"g_{g.id}",
                            "kind": "achieves",
                        }
                    )

            rel_doms_goal = [
                rd for rd in g.related_domains.all() if rd.id in domain_ids and rd.id != d.id
            ]
            if rel_doms_goal:
                cross_domain_items.append(
                    {
                        "item_type": "Goal",
                        "title": g.title,
                        "primary": d.name,
                        "related": [rd.name for rd in rel_doms_goal],
                    }
                )
                for rd in rel_doms_goal:
                    edges.append(
                        {
                            "source": f"g_{g.id}",
                            "target": f"d_{rd.id}",
                            "kind": "cross_domain",
                        }
                    )

    # Compute unexpressed Whys
    for d in domains:
        for w in d.whys.all():
            if w.id not in all_whys_with_objectives:
                unexpressed_whys.append(
                    {
                        "id": w.id,
                        "title": w.title,
                        "domain_name": d.name,
                        "is_non_negotiable": w.is_non_negotiable,
                    }
                )

    # Decision overlay
    decision_overlays = []
    for dec in decisions:
        supporting_obj_ids = [obj.id for obj in dec.supporting_objectives.all()]
        conflicting_obj_ids = [obj.id for obj in dec.conflicting_objectives.all()]
        decision_overlays.append(
            {
                "id": dec.id,
                "title": dec.title,
                "status": dec.status,
                "supporting_objectives": supporting_obj_ids,
                "conflicting_objectives": conflicting_obj_ids,
            }
        )

    return {
        "framework_id": framework.id,
        "framework_name": framework.name,
        "domain_count": len(domains),
        "prefetched_domains": domains,
        "nodes": nodes,
        "edges": edges,
        "diagnostics": {
            "unanchored_goals": unanchored_goals,
            "unexpressed_whys": unexpressed_whys,
            "cross_domain_items": cross_domain_items,
        },
        "decisions": decision_overlays,
    }
