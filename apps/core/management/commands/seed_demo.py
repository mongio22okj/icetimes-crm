from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.tests.factories import UserFactory
from apps.customers.tests.factories import CustomerFactory
from apps.orders.tests.factories import OrderFactory, OrderItemFactory
from apps.products.tests.factories import CategoryFactory, ProductFactory


class Command(BaseCommand):
    help = "Populate demo data for the Apex dashboard (users, products, orders)."

    def handle(self, *args, **opts):
        from django.conf import settings
        from django.utils import timezone

        User = get_user_model()
        demo_username = getattr(settings, "DEMO_USERNAME", "demo")
        demo_password = getattr(settings, "DEMO_PASSWORD", "ApexShowcase!2026")

        # 1. Demo user with known credentials (idempotent via get_or_create).
        # Password is always reset so re-running with a new DEMO_PASSWORD setting
        # picks up the change without manual intervention.
        demo, created = User.objects.get_or_create(
            username=demo_username,
            defaults={
                "email": "demo@example.com",
                "first_name": "Demo",
                "last_name": "User",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        demo.set_password(demo_password)
        demo.email_verified_at = timezone.now()
        # Superuser so the public demo can fully explore the themed Django
        # admin — every model, change form, inline, autocomplete, etc. Safe
        # because the hourly `reset_demo` cron flushes + reseeds, reverting
        # any visitor changes (including password/permission edits) on a
        # fixed schedule. Set explicitly (not just via defaults) so an
        # existing demo user gets upgraded on reseed.
        demo.is_staff = True
        demo.is_superuser = True
        demo.save()

        # 2. Batch users via factory (randomized, password="password").
        # Factory-produced emails might collide; suffix each with +<index>
        # and mark verified so the fixture doesn't need the verify flow.
        # Also enrich with title/location/bio so profile pages look real.
        from random import choice as _choice

        titles = [
            "Senior Engineer", "Product Designer", "Engineering Manager",
            "Customer Success", "Backend Engineer", "Frontend Engineer",
            "DevOps Lead", "QA Engineer", "Data Analyst", "Sales Lead",
            "UX Researcher", "Tech Lead", "Marketing Manager",
            "Account Executive", "Solutions Architect",
        ]
        locations = [
            "San Francisco, CA", "New York, NY", "Austin, TX",
            "London, UK", "Berlin, DE", "Toronto, CA", "Sydney, AU",
            "Amsterdam, NL", "Lisbon, PT", "Singapore",
            "Tokyo, JP", "Tel Aviv, IL", "Buenos Aires, AR",
        ]
        bios = [
            "Shipping pixels and pipelines.",
            "Working on the product surface and design system.",
            "Backend engineer. Likes databases and well-named functions.",
            "Helping customers get the most out of the product.",
            "Building delightful UI patterns and component primitives.",
            "Keeping the lights on and the deploys green.",
        ]
        for i in range(15):
            u = UserFactory()
            base, _, domain = u.email.partition("@")
            u.email = f"{base}+{i}@{domain or 'apex.local'}"
            u.email_verified_at = timezone.now()
            u.title = _choice(titles)
            u.location = _choice(locations)
            u.bio = _choice(bios)
            u.save(update_fields=["email", "email_verified_at",
                                  "title", "location", "bio"])

        # Demo user gets a richer profile too
        demo.title = "Founding Engineer"
        demo.location = "Remote · UTC+0"
        demo.bio = "Demo account — explore Apex with this signed-in profile."
        demo.website = "https://apex.example/"
        demo.save(update_fields=["title", "location", "bio", "website"])

        # 2c. Billing — give the demo account an active Pro subscription
        # with two saved cards so /billing/ shows real content.
        from datetime import timedelta as _td_billing
        from decimal import Decimal as _Dec

        from apps.billing.models import PaymentMethod as DemoPM
        from apps.billing.models import Subscription as DemoSub

        sub, _ = DemoSub.objects.get_or_create(
            user=demo,
            defaults={
                "plan": "pro", "status": "active", "billing_cycle": "monthly",
                "amount": _Dec("49"), "currency": "USD",
                "billing_email": demo.email,
                "started_at": timezone.now() - _td_billing(days=92),
                "renews_at": timezone.now() + _td_billing(days=18),
                "seats": 5,
                "usage_seats": 3,
                "usage_storage_gb": 24,
                "usage_api_calls": 87420,
            },
        )
        if not sub.payment_methods.exists():
            DemoPM.objects.create(
                subscription=sub, brand="visa", last4="4242",
                exp_month=12, exp_year=2028,
                cardholder="Demo User", is_default=True,
            )
            DemoPM.objects.create(
                subscription=sub, brand="mastercard", last4="5151",
                exp_month=8, exp_year=2027,
                cardholder="Demo User", is_default=False,
            )

        # 2b. Customers (separate from users — external people we sell to).
        # Bumped from 20 → 100 to give the Customers TableView a realistic
        # number of pages, filters, and sort interactions to play with.
        CustomerFactory.create_batch(100)

        # 3. Categories + products
        CategoryFactory.create_batch(5)
        ProductFactory.create_batch(25)

        # 4. Orders with items
        for _ in range(30):
            order = OrderFactory()
            for _ in range(3):
                OrderItemFactory(order=order)

        # 5. Invoices — mixed statuses, 1-4 line items each
        from datetime import timedelta
        from decimal import Decimal
        from random import randint

        from apps.customers.models import Customer
        from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

        customers_for_invoices = list(Customer.objects.all()[:15])
        status_spread = ["draft"] * 5 + ["sent"] * 5 + ["paid"] * 3 + ["void"] * 2
        today = timezone.now().date()
        for i, target_status in enumerate(status_spread):
            customer = customers_for_invoices[i % len(customers_for_invoices)]
            issue = today - timedelta(days=randint(1, 90))
            due = issue + timedelta(days=30)
            inv = InvoiceFactory(
                customer=customer,
                issue_date=issue,
                due_date=due,
                tax_rate=Decimal("10.00"),
                status="draft",
            )
            for _ in range(randint(1, 4)):
                InvoiceItemFactory(
                    invoice=inv,
                    quantity=randint(1, 5),
                    unit_price=Decimal(f"{randint(25, 500)}.99"),
                )
            if target_status == "sent":
                inv.mark_sent()
            elif target_status == "paid":
                inv.mark_sent()
                inv.mark_paid()
            elif target_status == "void":
                inv.mark_sent()
                inv.mark_void()

        # 6. Mail — generate ~30 messages between demo + a few staff senders.
        # Demo is the recipient most of the time so the inbox is populated.
        from random import choice, choices, randint

        from apps.mail.tests.factories import DraftFactory, MessageFactory

        # Promote 4 of the batch users to staff so demo can mail them
        mail_partners = list(User.objects.filter(is_staff=False)[:4])
        for u in mail_partners:
            u.is_staff = True
            u.save(update_fields=["is_staff"])

        # 20 received by demo (mix of read/unread/starred)
        for _ in range(20):
            sender = choice(mail_partners)
            MessageFactory(
                sender=sender,
                recipient=demo,
                is_read=choices([False, True], weights=[3, 7])[0],
                is_starred=choices([False, True], weights=[8, 2])[0],
            )
        # 8 sent by demo
        for _ in range(8):
            recipient = choice(mail_partners)
            MessageFactory(sender=demo, recipient=recipient)
        # 2 drafts
        for _ in range(2):
            DraftFactory(sender=demo, recipient=choice(mail_partners))
        # 2 trashed (received then trashed)
        for _ in range(2):
            MessageFactory(
                sender=choice(mail_partners), recipient=demo, is_trashed=True,
            )
        # One reply chain (root + reply)
        root = MessageFactory(sender=mail_partners[0], recipient=demo,
                              subject="Question about Q4")
        MessageFactory(
            sender=demo, recipient=mail_partners[0],
            subject="Re: Question about Q4",
            parent=root,
        )

        # 6.5 Calendar — ~12 events spread across the next ~30 days
        from datetime import timedelta as _td

        from apps.events.tests.factories import EventFactory

        categories = ["meeting", "personal", "deadline", "holiday"]
        for _ in range(12):
            offset_days = randint(-5, 25)
            start = timezone.now().replace(minute=0, second=0, microsecond=0) + _td(
                days=offset_days, hours=randint(8, 17),
            )
            duration_hours = choice([1, 1, 2, 2, 4])
            EventFactory(
                owner=demo,
                start=start,
                end=start + _td(hours=duration_hours),
                category=choice(categories),
                all_day=choice([False, False, False, True]),
            )

        # 6.7 Kanban — ~20 cards across 4 columns
        from apps.kanban.tests.factories import CardFactory

        priorities = ["low", "med", "med", "high"]
        all_staff = list(User.objects.filter(is_staff=True))
        column_counts = {"todo": 7, "in_progress": 6, "review": 4, "done": 5}
        for status, n in column_counts.items():
            for i in range(n):
                due_offset = randint(-3, 14)
                CardFactory(
                    status=status,
                    priority=choice(priorities),
                    position=i,
                    assignee=choice(all_staff + [None, None]),
                    due_date=(
                        timezone.now().date() + _td(days=due_offset)
                        if randint(0, 1) else None
                    ),
                    created_by=demo,
                )

        # 6.8 Files — sample folders + files for the browser
        from django.core.files.base import ContentFile

        from apps.files.models import File as DemoFile
        from apps.files.models import Folder as DemoFolder

        # get_or_create rather than create so a second seed_demo run is
        # idempotent. SQL Server's UNIQUE on (owner, parent, name) treats two
        # NULL parents as equal (Postgres does not), and either way a stable
        # demo folder set is what we want.
        docs, _ = DemoFolder.objects.get_or_create(owner=demo, parent=None, name="Documents")
        invoices_dir, _ = DemoFolder.objects.get_or_create(owner=demo, parent=docs, name="Invoices")
        DemoFolder.objects.get_or_create(owner=demo, parent=None, name="Photos")

        sample_files = [
            ("welcome.txt",     b"Welcome to your Apex demo files.\n",          "text/plain"),
            ("readme.md",       b"# Readme\nSample markdown file.\n",           "text/markdown"),
            ("notes.txt",       b"Random notes and thoughts.\n" * 20,           "text/plain"),
            ("Q4-summary.txt",  b"Q4 numbers go here.\n",                       "text/plain"),
            ("invoice-001.txt", b"INV-2026-0001\nTotal: $1,200\n",              "text/plain"),
        ]
        targets = [None, None, docs, docs, invoices_dir]
        for (name, content, ctype), folder in zip(sample_files, targets, strict=True):
            DemoFile.objects.create(
                owner=demo,
                folder=folder,
                file=ContentFile(content, name=name),
                original_name=name,
                size=len(content),
                content_type=ctype,
            )

        # 6.9 Projects — 6 projects spanning all statuses, tasks + milestones
        import random as _random
        from datetime import timedelta as _td2

        from apps.customers.models import Customer as DemoCustomer
        from apps.projects.models import Milestone as DemoMilestone
        from apps.projects.models import Project as DemoProject
        from apps.projects.models import ProjectTask as DemoTask

        all_customers = list(DemoCustomer.objects.all())
        project_specs = [
            ("Apex Dashboard Redesign",  "Refresh the design system and ship a new dashboard for Q2.",         "active",    "high"),
            ("Onboarding Flow Revamp",   "Cut signup-to-active time in half with a guided wizard.",             "active",    "med"),
            ("Mobile App MVP",           "Native iOS/Android client targeting parity with the web v1.",         "planning",  "high"),
            ("Q1 Analytics Cleanup",     "Audit existing dashboards, retire unused metrics, document funnels.", "completed", "low"),
            ("Internal Tools Migration", "Move legacy admin scripts to the new ops dashboard.",                  "on_hold",   "low"),
            ("Customer Portal v2",       "White-label the customer-facing portal with theming.",                 "active",    "med"),
        ]
        for name, desc, status, priority in project_specs:
            p = DemoProject.objects.create(
                name=name, description=desc, status=status, priority=priority,
                owner=demo,
                customer=choice(all_customers + [None]) if all_customers else None,
                start_date=timezone.now().date() - _td2(days=randint(10, 60)),
                due_date=timezone.now().date() + _td2(days=randint(15, 90)),
                budget=randint(5, 80) * 1000,
                progress=randint(10, 90) if status == "active" else (100 if status == "completed" else 0),
            )
            # team: owner + 2-4 random staff
            team_pool = [u for u in mail_partners if u.is_staff] + [demo]
            for member in [demo] + _random.sample(team_pool, min(4, len(team_pool))):
                p.team.add(member)
            # 4-9 tasks across statuses
            statuses = ["todo", "todo", "in_progress", "in_progress", "review", "done", "done"]
            for i in range(randint(4, 9)):
                DemoTask.objects.create(
                    project=p, title=f"{name[:18]}: task {i + 1}",
                    description="",
                    status=choice(statuses) if status != "completed" else "done",
                    priority=choice(["low", "med", "med", "high"]),
                    assignee=choice(team_pool + [None]),
                    due_date=timezone.now().date() + _td2(days=randint(-5, 30)) if randint(0, 1) else None,
                    position=i,
                )
            # 2-4 milestones, half completed
            for i in range(randint(2, 4)):
                completed = timezone.now() if i == 0 and status != "planning" else None
                DemoMilestone.objects.create(
                    project=p, title=f"Milestone {i + 1}",
                    due_date=timezone.now().date() + _td2(days=15 + i * 14),
                    completed_at=completed,
                    position=i,
                )

        # 6.10 Help center — categories + articles for the knowledge base.
        from apps.help.models import Article as DemoArticle
        from apps.help.models import Category as DemoCategory

        if not DemoCategory.objects.exists():
            help_categories = [
                ("Getting started",   "Set up your account and ship your first project.", "rocket",     "#16a34a", 1),
                ("Account & billing", "Plans, payments, invoices, and team seats.",        "dollar-sign","#0891b2", 2),
                ("Features",          "Deep dives on every Apex surface and shortcut.",    "package",    "#6366f1", 3),
                ("Integrations",      "Connect Apex to the rest of your stack.",           "rocket",     "#d97706", 4),
                ("API & developers",  "Endpoints, webhooks, SDKs, and rate limits.",       "activity",   "#be185d", 5),
                ("Troubleshooting",   "Solutions to the questions we get most often.",     "settings",   "#0369a1", 6),
            ]
            cat_lookup = {}
            for name, desc, icon, accent, pos in help_categories:
                c = DemoCategory.objects.create(
                    name=name, description=desc, icon=icon,
                    accent=accent, position=pos,
                )
                cat_lookup[name] = c

            sample_body = (
                "This is a demo article in the Apex help center. Replace this "
                "copy with your real documentation — articles support multiple "
                "paragraphs separated by blank lines.\n\n"
                "Each paragraph renders independently with comfortable line "
                "height for long-form reading. The sidebar shows related "
                "articles in the same category plus a directory of every "
                "category in the knowledge base.\n\n"
                "Search is full-text across title, summary, and body — try the "
                "search box at /help/search/ to see it in action."
            )

            articles = [
                ("Getting started",   "Quick start — your first 10 minutes",       "From zero to a populated dashboard in under 10 minutes.",      True,  840),
                ("Getting started",   "Inviting your first teammate",              "Send an invite, set their role, and watch them appear.",       False, 320),
                ("Getting started",   "Connecting your first integration",        "Hook up Stripe, Slack, or Google Workspace in two clicks.",    False, 410),
                ("Account & billing", "Changing your plan",                        "Upgrade, downgrade, or switch billing cycles.",                True,  1280),
                ("Account & billing", "Adding a payment method",                  "Cards, bank transfer, and ACH — what's supported.",            False, 540),
                ("Account & billing", "Reading your invoices",                     "Where to find them, what each line item means.",               False, 290),
                ("Account & billing", "Cancellation and refunds",                  "What happens when you cancel — and our refund policy.",        False, 470),
                ("Features",          "Setting up two-factor authentication",      "TOTP setup, recovery codes, and what to do if you lose them.", True,  920),
                ("Features",          "Customizing your dashboard",                "Stat cards, chart variants, and the command palette.",         False, 380),
                ("Features",          "Mastering the kanban board",                "Drag-and-drop, keyboard shortcuts, and column tricks.",        False, 450),
                ("Features",          "Working with projects and tasks",           "Milestones, team members, activity timeline.",                  False, 510),
                ("Integrations",      "Stripe — webhooks and metadata",            "Connecting your Stripe account and reading webhook payloads.", False, 220),
                ("Integrations",      "Slack — notifications and slash commands",  "Pipe your Apex events into Slack channels.",                   False, 180),
                ("API & developers",  "API authentication",                        "Personal access tokens, scopes, and rotation.",                 False, 350),
                ("API & developers",  "Rate limits and retries",                   "What happens when you hit the limit, and how to back off.",    False, 240),
                ("API & developers",  "Webhook signatures",                        "Verifying webhook signatures with HMAC-SHA256.",                False, 290),
                ("Troubleshooting",   "I can't sign in",                           "Password resets, 2FA recovery, and locked accounts.",          False, 1410),
                ("Troubleshooting",   "Charts aren't loading",                     "Browser cache, CDN, and a quick diagnostic.",                  False, 220),
                ("Troubleshooting",   "Why didn't my invoice send?",               "Common reasons, and how to retry.",                            False, 260),
            ]
            for cat_name, title, summary, featured, views in articles:
                DemoArticle.objects.create(
                    category=cat_lookup[cat_name],
                    title=title, summary=summary,
                    body=f"# {title}\n\n{summary}\n\n{sample_body}",
                    is_featured=featured, view_count=views,
                )

        # 6.11 Blog — public marketing posts with topics + authors.
        from datetime import timedelta as _td_blog

        from apps.blog.models import Post as BlogPost
        from apps.blog.models import Topic as BlogTopic

        if not BlogTopic.objects.exists():
            blog_topics_def = [
                ("Product",     "Releases and what shipped this week.",  "#16a34a"),
                ("Engineering", "Notes from the team building Apex.",    "#0891b2"),
                ("Tutorials",   "Step-by-step walkthroughs.",            "#6366f1"),
                ("Company",     "Hiring, milestones, and the road ahead.","#d97706"),
            ]
            blog_topics = {}
            for tname, tdesc, taccent in blog_topics_def:
                blog_topics[tname] = BlogTopic.objects.create(
                    name=tname, description=tdesc, accent=taccent,
                )

            authors = list(User.objects.filter(is_staff=True))[:5] or [demo]
            blog_body_template = (
                "Welcome to the Apex blog. This is a sample post used to "
                "demonstrate the post detail layout — header, hero, body "
                "with multiple paragraphs, author byline, and related posts.\n\n"
                "Each paragraph renders independently with comfortable line "
                "height for long-form reading. Markdown-like syntax isn't "
                "parsed in this template, but the body field accepts any "
                "string content and respects blank-line paragraph breaks.\n\n"
                "Replace this copy with your real product update, tutorial, "
                "or announcement. The model fields (title, summary, body, "
                "cover_emoji, topic, author, published_at) cover the common "
                "shape of CMS-style posts."
            )

            posts_def = [
                ("Product",     "Apex 2.4 — projects, profiles, and a redesigned activity feed",
                                "Today we're shipping our biggest release of the quarter: a full Projects app, rich profile pages, and a workspace-wide activity timeline.",
                                "🚀", True,  3,  4820),
                ("Engineering", "Why we picked HTMX over React for our admin",
                                "A pragmatic look at the trade-offs of HTMX + Alpine vs. a full SPA — and why server-rendered Django still wins for dashboards.",
                                "⚙️", True,  10, 3120),
                ("Tutorials",   "Set up Stripe webhooks in 5 minutes",
                                "A copy-paste-ready walkthrough for verifying signatures and routing events to the right handler.",
                                "💳", False, 18, 2240),
                ("Product",     "New: Subscription portal, payment methods, and plan changes",
                                "Self-serve billing is here. Manage your plan, payment methods, and cancellation flow without leaving the dashboard.",
                                "💎", False, 25, 1840),
                ("Engineering", "How we made our chart factories theme-aware",
                                "Dark mode is more than CSS — and ApexCharts needs explicit color resolution. Here's how we wired it up.",
                                "🌗", False, 32, 1430),
                ("Tutorials",   "Building a custom kanban board with SortableJS",
                                "Drag-between-columns, server-side persistence, and accessibility — all in 80 lines of Alpine.",
                                "🎯", False, 40, 1180),
                ("Company",     "We raised our seed round to make Apex the best dashboard template",
                                "We're thrilled to share that we've raised $4.2M to keep building the best dashboard starter kit on the market.",
                                "🌱", False, 60, 5240),
                ("Product",     "Help center launch — answers to your top questions",
                                "Our brand-new help center surfaces 19+ articles across 6 categories with full-text search.",
                                "📚", False, 50, 1920),
                ("Engineering", "Designing tokens with OKLCh — what we learned",
                                "OKLCh gives us perceptually uniform color, but the tooling is still rough around the edges.",
                                "🎨", False, 75, 980),
            ]
            for tname, title, summary, emoji, featured, days_ago, views in posts_def:
                BlogPost.objects.create(
                    title=title, summary=summary,
                    body=blog_body_template,
                    cover_emoji=emoji,
                    topic=blog_topics.get(tname),
                    author=choice(authors),
                    is_featured=featured,
                    published_at=timezone.now() - _td_blog(days=days_ago),
                    view_count=views,
                )

        # 7. Chat — short conversations between demo and the mail partners.
        from apps.chat.tests.factories import ChatMessageFactory

        for partner in mail_partners[:3]:  # 3 active conversations
            # 4-8 messages, alternating sender, spread over the last day
            count = randint(4, 8)
            for i in range(count):
                if i % 2 == 0:
                    sender, recipient = partner, demo
                    is_read = i < count - 2  # last couple unread
                else:
                    sender, recipient = demo, partner
                    is_read = True
                ChatMessageFactory(
                    sender=sender, recipient=recipient,
                    is_read=is_read,
                )

        # 7.5 Organizations — give demo a default workspace, two extras to
        # demonstrate the switcher, plus a couple of memberships so the
        # Members page has real rows.
        from apps.organizations.models import (
            Invitation as DemoInvitation,
        )
        from apps.organizations.models import (
            Membership as DemoMembership,
        )
        from apps.organizations.models import (
            Organization as DemoOrg,
        )

        org_specs = [
            ("Apex Demo Co.",   "pro"),
            ("Side Project",    "free"),
            ("Acme Holdings",   "enterprise"),
        ]
        primary_org = None
        for org_name, plan in org_specs:
            org, _ = DemoOrg.objects.get_or_create(
                name=org_name,
                defaults={"plan": plan, "created_by": demo},
            )
            if primary_org is None:
                primary_org = org
            DemoMembership.objects.get_or_create(
                user=demo, organization=org,
                defaults={"role": "owner"},
            )

        # Add 3 random staff as members on the primary org.
        for u, role in zip(
            mail_partners[:3], ["admin", "member", "billing"], strict=False,
        ):
            DemoMembership.objects.get_or_create(
                user=u, organization=primary_org,
                defaults={"role": role},
            )

        # One pending invitation so the Members page shows the empty-but-not
        # state for invitations.
        if not primary_org.invitations.filter(
            email="pending@example.com",
        ).exists():
            DemoInvitation.create_for(
                primary_org,
                email="pending@example.com",
                role="member",
                invited_by=demo,
            )

        # 8. Notification trimming — Order/Invoice/Mail/Chat emits create rows
        # per staff user. With demo + 4 mail partners as staff, plus all the
        # auto-emits from prior steps, the count gets large. Mark the older
        # two-thirds as read so the bell badge stays digestible.
        from apps.notifications.models import Notification

        all_notes = list(Notification.objects.order_by("-created_at"))
        mark_read_pks = [n.pk for n in all_notes[len(all_notes) // 3:]]
        Notification.objects.filter(pk__in=mark_read_pks).update(read_at=timezone.now())

        self.stdout.write(self.style.SUCCESS(
            f"Seeded. Demo login: {demo_username} / {demo_password}"
        ))
