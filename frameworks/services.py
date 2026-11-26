from decisions.models import DecisionRecord, DecisionStatus, LLMReflectionLog
from frameworks.models import Domain, Framework, Goal, Objective, StatusChoices, Why


def seed_sample_framework(user) -> Framework:
    """Populates an illustrative sample framework clearly flagged with is_sample=True."""
    framework = Framework.objects.create(
        owner=user,
        name="Sample Life & Priorities Framework",
        description=(
            "Illustrative starter framework demonstrating Domains, Whys, Objectives, and Goals."
        ),
        is_sample=True,
    )

    # Domain 1: Family and Home
    family = Domain.objects.create(
        framework=framework,
        name="Family and Home",
        description=(
            "Broad sphere covering domestic stability, relationships, and caring responsibilities."
        ),
        display_order=1,
        is_sample=True,
    )
    why_family_1 = Why.objects.create(
        domain=family,
        title="To provide a secure and loving home for my family.",
        description="Core conviction that loved ones need warmth, emotional presence, and safety.",
        is_non_negotiable=True,
        display_order=1,
        is_sample=True,
    )
    why_family_2 = Why.objects.create(
        domain=family,
        title="To be present and actively involved in everyday family life.",
        description="Ensuring career or side interests do not crowd out unhurried time together.",
        is_non_negotiable=False,
        display_order=2,
        is_sample=True,
    )

    # Domain 2: Work and Vocation
    work = Domain.objects.create(
        framework=framework,
        name="Work and Vocation",
        description="Professional contribution, skills development, and financial stewardship.",
        display_order=2,
        is_sample=True,
    )
    Why.objects.create(
        domain=work,
        title="To contribute something worthwhile and intellectually honest through my work.",
        description="Finding meaning in craft, integrity, and serving real human needs.",
        is_non_negotiable=False,
        display_order=1,
        is_sample=True,
    )
    why_work_2 = Why.objects.create(
        domain=work,
        title="To provide financial resilience and support family independence.",
        description="Earning reliably to meet responsibilities without reckless overcommitment.",
        is_non_negotiable=True,
        display_order=2,
        is_sample=True,
    )

    # Domain 3: Personal Health and Well-being
    health = Domain.objects.create(
        framework=framework,
        name="Personal Health and Well-being",
        description="Physical endurance, mental clarity, rest, and renewal.",
        display_order=3,
        is_sample=True,
    )
    why_health = Why.objects.create(
        domain=health,
        title="To steward physical and mental health to sustain other commitments.",
        description="Recognizing that energy and health are foundations for everything else.",
        is_non_negotiable=False,
        display_order=1,
        is_sample=True,
    )

    # Objectives
    obj_financial = Objective.objects.create(
        primary_domain=work,
        title="Build financial resilience and a stable home environment.",
        description="Create margin against unexpected crises or downturns.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    obj_financial.whys.add(why_family_1, why_work_2)
    obj_financial.related_domains.add(family)

    obj_family_time = Objective.objects.create(
        primary_domain=family,
        title="Protect consistent, unhurried time with family each week.",
        description="Maintain clear boundaries between work hours and home life.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    obj_family_time.whys.add(why_family_2)
    obj_family_time.related_domains.add(work)

    obj_fitness = Objective.objects.create(
        primary_domain=health,
        title="Sustain cardiovascular fitness and regular rest cycles.",
        description="Maintain energy levels through routine movement and decent sleep.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    obj_fitness.whys.add(why_health)

    # Goals
    goal_fund = Goal.objects.create(
        primary_domain=work,
        title="Establish an emergency buffer of £10,000 over two years.",
        description="Save regularly into a high-yield liquid account.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    goal_fund.objectives.add(obj_financial)
    goal_fund.related_domains.add(family)

    goal_evenings = Goal.objects.create(
        primary_domain=family,
        title="Protect two work-free evenings each week for dinner and connection.",
        description="Close laptop by 6:00pm on Tuesdays and Thursdays.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    goal_evenings.objectives.add(obj_family_time)
    goal_evenings.related_domains.add(work)

    # Sample Decision Assessment demonstrating cross-domain tensions (§8.3 & §11.2)
    dec = DecisionRecord.objects.create(
        framework=framework,
        title="Senior Director Promotion with Extensive Travel",
        proposal_description=(
            "Offered a 30% salary increase to step up into Senior Director role, "
            "requiring two weeks of international travel each month and evening calls."
        ),
        benefits_and_costs=(
            "Benefits: Accelerates emergency fund goal by 18 months.\n"
            "Costs: Directly fractures unhurried family dinners and disrupts sleep rhythms."
        ),
        alternatives_considered=(
            "1. Negotiate remote-first role with capped travel (max 4 days/month).\n"
            "2. Decline promotion and seek local consulting clients."
        ),
        unresolved_questions=(
            "Can the travel obligations be shared with an overseas co-lead after 6 months?"
        ),
        decision_outcome=(
            "Counter-proposed alternative 1. If non-negotiable on travel, decline to preserve "
            "family evening commitments."
        ),
        status=DecisionStatus.DECIDED,
    )
    dec.affected_domains.add(family, work, health)
    dec.relevant_whys.add(why_family_2, why_work_2, why_health)
    dec.supporting_objectives.add(obj_financial)
    dec.conflicting_objectives.add(obj_family_time, obj_fitness)

    # Sample Thinking Partner Reflection Log (§8.3)
    LLMReflectionLog.objects.create(
        framework=framework,
        decision=dec,
        user_prompt="Examine the core tensions between my financial goals and family presence.",
        context_snapshot=(
            "**Primary Domain:** Work and Vocation\n"
            "- Supporting Objective: Build financial resilience\n"
            "- Conflicting Objective: Protect unhurried time with family"
        ),
        llm_response=(
            "### Reflection on Tensions\n\n"
            "1. **Core Value Alignment:** Family presence is vital to everyday life. "
            "The proposed travel schedule directly conflicts with this.\n"
            "2. **Alternative Viability:** Proposing capped travel allows testing whether the "
            "organisation values strategic leadership rather than physical presence.\n"
            "3. **Long-Term Trajectory:** Financial gain that compromises family stability "
            "contradicts your fundamental definition of financial stewardship."
        ),
        provider_used="Ollama (Local / Llama 3.1)",
    )

    return framework


def seed_career_transition_framework(user) -> Framework:
    """Starter template: Career & Vocation Transition."""
    framework = Framework.objects.create(
        owner=user,
        name="Career & Vocation Transition",
        description=(
            "Framework designed for exploring new professional directions, startup ventures, "
            "or sabbatical planning."
        ),
        is_sample=True,
    )

    domain_craft = Domain.objects.create(
        framework=framework,
        name="Creative Craft & Autonomy",
        description="Deep work, autonomy in problem selection, and mastery.",
        display_order=1,
        is_sample=True,
    )
    why_craft = Why.objects.create(
        domain=domain_craft,
        title="To spend my working hours on problems that genuinely intrigue me.",
        description="Avoiding bureaucratic overhead in favor of direct creative impact.",
        is_non_negotiable=True,
        display_order=1,
        is_sample=True,
    )

    domain_finances = Domain.objects.create(
        framework=framework,
        name="Runway & Financial Freedom",
        description="Maintaining financial independence during times of uncertainty.",
        display_order=2,
        is_sample=True,
    )
    why_finances = Why.objects.create(
        domain=domain_finances,
        title="To maintain a clear financial runway before committing to full autonomy.",
        description="Preventing financial panic from forcing compromises on integrity.",
        is_non_negotiable=True,
        display_order=1,
        is_sample=True,
    )

    obj_mvp = Objective.objects.create(
        primary_domain=domain_craft,
        title="Validate prototype product with 50 paying customers.",
        description="Prove commercial and practical utility before leaving stable employment.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    obj_mvp.whys.add(why_craft, why_finances)

    Goal.objects.create(
        primary_domain=domain_craft,
        title="Launch closed beta of product within 90 days.",
        description="Interview 10 target users weekly.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    return framework


def seed_creator_framework(user) -> Framework:
    """Starter template: Independent Creator & Sustainable Pace."""
    framework = Framework.objects.create(
        owner=user,
        name="Independent Creator & Sustainable Pace",
        description=(
            "Balancing creative output, personal rest, and sustainable commercial operations."
        ),
        is_sample=True,
    )

    domain_work = Domain.objects.create(
        framework=framework,
        name="Publication & Expression",
        description="Consistent writing, research, and independent publishing.",
        display_order=1,
        is_sample=True,
    )
    why_work = Why.objects.create(
        domain=domain_work,
        title="To communicate thoughtful, enduring ideas clearly and generously.",
        description="Writing without chasing sensationalism or algorithm changes.",
        is_non_negotiable=True,
        display_order=1,
        is_sample=True,
    )

    domain_rest = Domain.objects.create(
        framework=framework,
        name="Sabbath & Regeneration",
        description="Protecting weekly rest, quiet reading, and digital detours.",
        display_order=2,
        is_sample=True,
    )
    why_rest = Why.objects.create(
        domain=domain_rest,
        title="To prevent chronic burnout through deliberate deceleration.",
        description="Recognizing that insight requires spacious thinking time.",
        is_non_negotiable=True,
        display_order=1,
        is_sample=True,
    )

    obj_essays = Objective.objects.create(
        primary_domain=domain_work,
        title="Publish 12 high-depth longform essays per year.",
        description="Focus on timeless clarity rather than weekly commentary.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    obj_essays.whys.add(why_work, why_rest)
    obj_essays.related_domains.add(domain_rest)

    Goal.objects.create(
        primary_domain=domain_rest,
        title="Take every Sunday entirely offline with zero screens.",
        description="Dedicate the day to walks, books, and family conversation.",
        status=StatusChoices.ACTIVE,
        is_sample=True,
    )
    return framework


def remove_sample_frameworks(user) -> int:
    """Removes all sample frameworks and items owned by the user."""
    sample_frameworks = Framework.objects.filter(owner=user, is_sample=True)
    count = sample_frameworks.count()
    sample_frameworks.delete()
    return count

