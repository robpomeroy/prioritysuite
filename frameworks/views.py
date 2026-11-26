from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from frameworks.forms import DomainForm, FrameworkForm, GoalForm, ObjectiveForm, WhyForm
from frameworks.models import Domain, Framework, Goal, Objective, StatusChoices, Why
from frameworks.services import remove_sample_frameworks, seed_sample_framework


def _get_user_framework(user, framework_id=None):
    if framework_id:
        return get_object_or_404(Framework, id=framework_id, owner=user)
    fw = Framework.objects.filter(owner=user).order_by("name").first()
    if not fw:
        fw = Framework.objects.create(owner=user, name="My Personal Priorities")
    return fw


@login_required
def workspace_view(request, framework_id=None):
    framework = _get_user_framework(request.user, framework_id)
    user_frameworks = Framework.objects.filter(owner=request.user).order_by("name")
    domains = framework.domains.prefetch_related(
        "whys",
        "primary_objectives__whys",
        "primary_objectives__related_domains",
        "primary_goals__objectives",
        "primary_goals__related_domains",
    ).all()

    return render(
        request,
        "frameworks/workspace.html",
        {
            "framework": framework,
            "user_frameworks": user_frameworks,
            "domains": domains,
        },
    )


@login_required
def seed_sample_view(request):
    if request.method == "POST":
        fw = seed_sample_framework(request.user)
        messages.success(
            request, f"Loaded sample framework '{fw.name}'. You can modify or remove it anytime."
        )
        return redirect("frameworks:workspace_detail", framework_id=fw.id)
    return redirect("frameworks:workspace")


@login_required
def remove_sample_view(request):
    if request.method == "POST":
        count = remove_sample_frameworks(request.user)
        messages.info(request, f"Removed {count} sample framework(s).")
        return redirect("frameworks:workspace")
    return redirect("frameworks:workspace")


@login_required
def framework_create_view(request):
    if request.method == "POST":
        form = FrameworkForm(request.POST)
        if form.is_valid():
            framework = form.save(commit=False)
            framework.owner = request.user
            framework.save()
            messages.success(request, f"Framework '{framework.name}' created.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = FrameworkForm()
    return render(
        request,
        "frameworks/form_modal.html",
        {"form": form, "title": "Create New Framework"},
    )


@login_required
def framework_edit_view(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    if request.method == "POST":
        form = FrameworkForm(request.POST, instance=framework)
        if form.is_valid():
            form.save()
            messages.success(request, f"Framework '{framework.name}' updated.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = FrameworkForm(instance=framework)
    return render(
        request,
        "frameworks/form_modal.html",
        {"form": form, "title": f"Edit Framework: {framework.name}"},
    )


@login_required
def framework_delete_view(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    if request.method == "POST":
        name = framework.name
        framework.delete()
        messages.info(request, f"Framework '{name}' was deleted.")
        return redirect("frameworks:workspace")
    return render(
        request,
        "frameworks/confirm_delete.html",
        {"item_type": "Framework", "item_name": framework.name},
    )


@login_required
def domain_create_view(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    if request.method == "POST":
        form = DomainForm(request.POST)
        if form.is_valid():
            domain = form.save(commit=False)
            domain.framework = framework
            domain.save()
            messages.success(request, f"Added domain '{domain.name}'.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = DomainForm()
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": "Add New Domain",
            "cancel_url": reverse("frameworks:workspace_detail", args=[framework.id]),
        },
    )


@login_required
def domain_edit_view(request, domain_id):
    domain = get_object_or_404(Domain, id=domain_id, framework__owner=request.user)
    if request.method == "POST":
        form = DomainForm(request.POST, instance=domain)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated domain '{domain.name}'.")
            return redirect("frameworks:workspace_detail", framework_id=domain.framework_id)
    else:
        form = DomainForm(instance=domain)
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": f"Edit Domain: {domain.name}",
            "cancel_url": reverse("frameworks:workspace_detail", args=[domain.framework_id]),
        },
    )


@login_required
def domain_delete_view(request, domain_id):
    domain = get_object_or_404(Domain, id=domain_id, framework__owner=request.user)
    fw_id = domain.framework_id
    if request.method == "POST":
        name = domain.name
        domain.delete()
        messages.info(request, f"Domain '{name}' and its child items were deleted.")
        return redirect("frameworks:workspace_detail", framework_id=fw_id)
    return render(
        request,
        "frameworks/confirm_delete.html",
        {
            "item_type": "Domain",
            "item_name": domain.name,
            "cancel_url": reverse("frameworks:workspace_detail", args=[fw_id]),
        },
    )


@login_required
def why_create_view(request, domain_id):
    domain = get_object_or_404(Domain, id=domain_id, framework__owner=request.user)
    if request.method == "POST":
        form = WhyForm(request.POST)
        if form.is_valid():
            why = form.save(commit=False)
            why.domain = domain
            why.save()
            messages.success(request, "Added Why.")
            return redirect("frameworks:workspace_detail", framework_id=domain.framework_id)
    else:
        form = WhyForm()
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": f"Add Why in {domain.name}",
            "guidance": "Why does this area matter to you? Why should anything happen here?",
            "cancel_url": reverse("frameworks:workspace_detail", args=[domain.framework_id]),
        },
    )


@login_required
def why_edit_view(request, why_id):
    why = get_object_or_404(Why, id=why_id, domain__framework__owner=request.user)
    if request.method == "POST":
        form = WhyForm(request.POST, instance=why)
        if form.is_valid():
            form.save()
            messages.success(request, "Updated Why.")
            return redirect("frameworks:workspace_detail", framework_id=why.domain.framework_id)
    else:
        form = WhyForm(instance=why)
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": "Edit Why",
            "cancel_url": reverse("frameworks:workspace_detail", args=[why.domain.framework_id]),
        },
    )


@login_required
def why_delete_view(request, why_id):
    why = get_object_or_404(Why, id=why_id, domain__framework__owner=request.user)
    fw_id = why.domain.framework_id
    if request.method == "POST":
        why.delete()
        messages.info(request, "Why deleted.")
        return redirect("frameworks:workspace_detail", framework_id=fw_id)
    return render(
        request,
        "frameworks/confirm_delete.html",
        {
            "item_type": "Why",
            "item_name": why.title,
            "cancel_url": reverse("frameworks:workspace_detail", args=[fw_id]),
        },
    )


@login_required
def objective_create_view(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    initial_domain_id = request.GET.get("domain_id")
    initial = {"primary_domain": initial_domain_id} if initial_domain_id else {}
    if request.method == "POST":
        form = ObjectiveForm(request.POST, framework=framework)
        if form.is_valid():
            form.save()
            messages.success(request, "Created objective.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = ObjectiveForm(framework=framework, initial=initial)
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": "Add New Objective",
            "guidance": "What would you like your Whys to lead to?",
            "cancel_url": reverse("frameworks:workspace_detail", args=[framework.id]),
        },
    )


@login_required
def objective_edit_view(request, objective_id):
    objective = get_object_or_404(
        Objective, id=objective_id, primary_domain__framework__owner=request.user
    )
    framework = objective.primary_domain.framework
    if request.method == "POST":
        form = ObjectiveForm(request.POST, instance=objective, framework=framework)
        if form.is_valid():
            form.save()
            messages.success(request, "Updated objective.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = ObjectiveForm(instance=objective, framework=framework)
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": "Edit Objective",
            "cancel_url": reverse("frameworks:workspace_detail", args=[framework.id]),
        },
    )


@login_required
def objective_delete_view(request, objective_id):
    objective = get_object_or_404(
        Objective, id=objective_id, primary_domain__framework__owner=request.user
    )
    fw_id = objective.primary_domain.framework_id
    if request.method == "POST":
        objective.delete()
        messages.info(request, "Objective deleted.")
        return redirect("frameworks:workspace_detail", framework_id=fw_id)
    return render(
        request,
        "frameworks/confirm_delete.html",
        {
            "item_type": "Objective",
            "item_name": objective.title,
            "cancel_url": reverse("frameworks:workspace_detail", args=[fw_id]),
        },
    )


@login_required
def goal_create_view(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    initial_domain_id = request.GET.get("domain_id")
    initial = {"primary_domain": initial_domain_id} if initial_domain_id else {}
    if request.method == "POST":
        form = GoalForm(request.POST, framework=framework)
        if form.is_valid():
            form.save()
            messages.success(request, "Created goal.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = GoalForm(framework=framework, initial=initial)
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": "Add New Goal",
            "guidance": "What specifically will you do or achieve?",
            "cancel_url": reverse("frameworks:workspace_detail", args=[framework.id]),
        },
    )


@login_required
def goal_edit_view(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id, primary_domain__framework__owner=request.user)
    framework = goal.primary_domain.framework
    if request.method == "POST":
        form = GoalForm(request.POST, instance=goal, framework=framework)
        if form.is_valid():
            form.save()
            messages.success(request, "Updated goal.")
            return redirect("frameworks:workspace_detail", framework_id=framework.id)
    else:
        form = GoalForm(instance=goal, framework=framework)
    return render(
        request,
        "frameworks/form_modal.html",
        {
            "form": form,
            "title": "Edit Goal",
            "cancel_url": reverse("frameworks:workspace_detail", args=[framework.id]),
        },
    )


@login_required
def goal_delete_view(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id, primary_domain__framework__owner=request.user)
    fw_id = goal.primary_domain.framework_id
    if request.method == "POST":
        goal.delete()
        messages.info(request, "Goal deleted.")
        return redirect("frameworks:workspace_detail", framework_id=fw_id)
    return render(
        request,
        "frameworks/confirm_delete.html",
        {
            "item_type": "Goal",
            "item_name": goal.title,
            "cancel_url": reverse("frameworks:workspace_detail", args=[fw_id]),
        },
    )


def _reorder_sibling_items(items, target_item, direction):
    idx = items.index(target_item)
    target_idx = None
    if direction == "up" and idx > 0:
        target_idx = idx - 1
    elif direction == "down" and idx < len(items) - 1:
        target_idx = idx + 1

    if target_idx is not None:
        items[idx], items[target_idx] = items[target_idx], items[idx]
        for new_order, item in enumerate(items, start=1):
            if item.display_order != new_order:
                item.display_order = new_order
                item.save(update_fields=["display_order"])


def _handle_status_update(request, item, label):
    new_status = request.POST.get("status")
    if new_status in StatusChoices.values:
        item.status = new_status
        item.save(update_fields=["status", "updated_at"])
        messages.success(request, f"{label} status changed to {item.get_status_display()}.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("frameworks:workspace_detail", framework_id=item.primary_domain.framework_id)


@login_required
def domain_move_view(request, domain_id, direction):
    if request.method != "POST":
        return HttpResponseForbidden()
    with transaction.atomic():
        domain = get_object_or_404(Domain, id=domain_id, framework__owner=request.user)
        fw = Framework.objects.select_for_update().get(id=domain.framework_id)
        all_domains = list(fw.domains.order_by("display_order", "id"))
        _reorder_sibling_items(all_domains, domain, direction)

    return redirect("frameworks:workspace_detail", framework_id=domain.framework_id)


@login_required
def why_move_view(request, why_id, direction):
    if request.method != "POST":
        return HttpResponseForbidden()
    with transaction.atomic():
        why = get_object_or_404(Why, id=why_id, domain__framework__owner=request.user)
        dom = Domain.objects.select_for_update().get(id=why.domain_id)
        all_whys = list(dom.whys.order_by("display_order", "id"))
        _reorder_sibling_items(all_whys, why, direction)

    return redirect("frameworks:workspace_detail", framework_id=why.domain.framework_id)


@login_required
def objective_status_view(request, objective_id):
    if request.method != "POST":
        return HttpResponseForbidden()
    obj = get_object_or_404(
        Objective, id=objective_id, primary_domain__framework__owner=request.user
    )
    return _handle_status_update(request, obj, "Objective")


@login_required
def goal_status_view(request, goal_id):
    if request.method != "POST":
        return HttpResponseForbidden()
    goal = get_object_or_404(Goal, id=goal_id, primary_domain__framework__owner=request.user)
    return _handle_status_update(request, goal, "Goal")


@login_required
def review_view(request, framework_id=None):
    framework = _get_user_framework(request.user, framework_id)
    status_filter = request.GET.get("status", "")
    age_filter = request.GET.get("age", "")
    today = timezone.now().date()

    whys = Why.objects.filter(domain__framework=framework).select_related("domain")
    objectives = Objective.objects.filter(primary_domain__framework=framework).select_related(
        "primary_domain"
    )
    goals = Goal.objects.filter(primary_domain__framework=framework).select_related(
        "primary_domain"
    )

    if status_filter:
        objectives = objectives.filter(status=status_filter)
        goals = goals.filter(status=status_filter)

    if age_filter == "never":
        whys = whys.filter(last_reviewed_at__isnull=True)
        objectives = objectives.filter(last_reviewed_at__isnull=True)
        goals = goals.filter(last_reviewed_at__isnull=True)
    elif age_filter in ("90", "180", "365"):
        days = int(age_filter)
        cutoff = today - timedelta(days=days)
        whys = whys.filter(last_reviewed_at__isnull=False, last_reviewed_at__lt=cutoff)
        objectives = objectives.filter(last_reviewed_at__isnull=False, last_reviewed_at__lt=cutoff)
        goals = goals.filter(last_reviewed_at__isnull=False, last_reviewed_at__lt=cutoff)

    user_frameworks = Framework.objects.filter(owner=request.user).order_by("name")

    return render(
        request,
        "frameworks/review.html",
        {
            "framework": framework,
            "user_frameworks": user_frameworks,
            "whys": whys,
            "objectives": objectives,
            "goals": goals,
            "status_filter": status_filter,
            "age_filter": age_filter,
            "StatusChoices": StatusChoices,
        },
    )


@login_required
def mark_all_reviewed_view(request, framework_id):
    if request.method != "POST":
        return HttpResponseForbidden()
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    today = timezone.now().date()
    with transaction.atomic():
        Why.objects.filter(domain__framework=framework).update(last_reviewed_at=today)
        Objective.objects.filter(primary_domain__framework=framework).update(
            last_reviewed_at=today
        )
        Goal.objects.filter(primary_domain__framework=framework).update(last_reviewed_at=today)
    messages.success(request, f"Marked all framework items as reviewed on {today}.")
    return redirect("frameworks:review_detail", framework_id=framework.id)


@login_required
def mark_reviewed_view(request, item_type, item_id):
    if request.method == "POST":
        today = timezone.now().date()
        if item_type == "why":
            item = get_object_or_404(Why, id=item_id, domain__framework__owner=request.user)
        elif item_type == "objective":
            item = get_object_or_404(
                Objective, id=item_id, primary_domain__framework__owner=request.user
            )
        elif item_type == "goal":
            item = get_object_or_404(
                Goal, id=item_id, primary_domain__framework__owner=request.user
            )
        else:
            return HttpResponseForbidden()
        item.last_reviewed_at = today
        item.save(update_fields=["last_reviewed_at", "updated_at"])
        if request.headers.get("HX-Request"):
            return HttpResponse(f"<span class='badge bg-sage text-white'>Reviewed {today}</span>")
        messages.success(request, f"Marked as reviewed on {today}.")
        return redirect(
            "frameworks:review_detail",
            framework_id=item.domain.framework_id
            if hasattr(item, "domain")
            else item.primary_domain.framework_id,
        )
    return HttpResponseForbidden()


@login_required
def template_library_view(request):
    """Gallery of predefined life framework templates."""
    from frameworks.services import FRAMEWORK_TEMPLATES

    return render(
        request,
        "frameworks/template_library.html",
        {"templates": FRAMEWORK_TEMPLATES},
    )


@login_required
def template_apply_view(request, slug):
    """Instantiates a chosen framework template for the user."""
    if request.method != "POST":
        return redirect("frameworks:template_library")

    as_sample = request.POST.get("as_sample", "").lower() == "true"
    from frameworks.services import seed_template_by_slug

    try:
        fw = seed_template_by_slug(request.user, slug, as_sample=as_sample)
        messages.success(
            request,
            f"Instantiated '{fw.name}'. You can explore and modify it in your Workspace.",
        )
        return redirect("frameworks:workspace_detail", framework_id=fw.id)
    except ValueError as err:
        messages.error(request, str(err))
        return redirect("frameworks:template_library")


@login_required
def framework_map_view(request, framework_id=None):
    """Interactive visual relationship map and alignment diagnostics."""
    framework = _get_user_framework(request.user, framework_id)
    user_frameworks = Framework.objects.filter(owner=request.user).order_by("name")
    from frameworks.visualization import build_framework_graph

    graph_data = build_framework_graph(framework)
    return render(
        request,
        "frameworks/map.html",
        {
            "framework": framework,
            "user_frameworks": user_frameworks,
            "graph_data": graph_data,
        },
    )


@login_required
def snapshot_list_view(request, framework_id=None):
    """Lists saved historical snapshots for a framework."""
    framework = _get_user_framework(request.user, framework_id)
    user_frameworks = Framework.objects.filter(owner=request.user).order_by("name")
    snapshots = framework.snapshots.all()

    return render(
        request,
        "frameworks/history.html",
        {
            "framework": framework,
            "user_frameworks": user_frameworks,
            "snapshots": snapshots,
        },
    )


@login_required
def snapshot_create_view(request, framework_id):
    """Captures a point-in-time snapshot of the framework."""
    if request.method != "POST":
        return redirect("frameworks:snapshot_list", framework_id=framework_id)

    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    title = (request.POST.get("title") or "").strip() or "Unnamed Snapshot"
    notes = (request.POST.get("notes") or "").strip()

    from frameworks.comparison import serialize_framework_for_snapshot
    from frameworks.models import FrameworkSnapshot

    data = serialize_framework_for_snapshot(framework)
    snap = FrameworkSnapshot.objects.create(
        framework=framework,
        title=title,
        notes=notes,
        snapshot_data=data,
    )
    messages.success(request, f"Saved snapshot '{snap.title}'.")
    return redirect("frameworks:snapshot_list", framework_id=framework.id)


@login_required
def snapshot_compare_view(request, framework_id, snapshot_id):
    """Compares a historical snapshot against current live framework data."""
    framework = get_object_or_404(Framework, id=framework_id, owner=request.user)
    snapshot = get_object_or_404(
        framework.snapshots.model, id=snapshot_id, framework=framework
    )

    from frameworks.comparison import (
        compare_framework_states,
        serialize_framework_for_snapshot,
    )

    live_state = serialize_framework_for_snapshot(framework)
    diff = compare_framework_states(snapshot.snapshot_data, live_state)

    return render(
        request,
        "frameworks/snapshot_compare.html",
        {
            "framework": framework,
            "snapshot": snapshot,
            "diff": diff,
        },
    )


@login_required
def snapshot_delete_view(request, snapshot_id):
    """Deletes a historical snapshot."""
    from frameworks.models import FrameworkSnapshot

    snap = get_object_or_404(
        FrameworkSnapshot, id=snapshot_id, framework__owner=request.user
    )
    fw_id = snap.framework_id
    title = snap.title
    if request.method == "POST":
        snap.delete()
        messages.info(request, f"Deleted snapshot '{title}'.")
    return redirect("frameworks:snapshot_list", framework_id=fw_id)

