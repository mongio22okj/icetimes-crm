import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0004_campaign"),
    ]

    operations = [
        # ── Lead.score ─────────────────────────────────────────────────
        migrations.AddField(
            model_name="lead",
            name="score",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Qualità del lead 0-100. Calcolato automaticamente in base alla completezza/validità dei dati al postback.",
            ),
        ),

        # ── LeadSource: dispatch + payout + dedup ─────────────────────
        migrations.AddField(
            model_name="leadsource",
            name="priority",
            field=models.PositiveIntegerField(
                default=100, db_index=True,
                help_text="Ordine ping-tree: numero più basso = priorità più alta. Il dispatch prova prima il broker con priority minore.",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="auto_dispatch",
            field=models.BooleanField(
                default=False,
                help_text="Se ON, al postback il CRM avvia automaticamente il dispatch ping-tree per leads ricevuti da questo source.",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="payout_per_ftd",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                help_text="Quanto ti paga il broker per ogni FTD verificato.",
                verbose_name="Payout per FTD (€)",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="payout_per_lead",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                help_text="Quanto ti paga il broker per ogni lead consegnato (anche senza FTD).",
                verbose_name="Payout per lead (€)",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="duplicate_window_hours",
            field=models.PositiveIntegerField(
                default=24,
                help_text="Un lead con stessa email/uniqueid arrivato entro N ore viene marcato come duplicato. 0 = disabilita controllo.",
                verbose_name="Finestra antiduplicato (ore)",
            ),
        ),
        migrations.AlterModelOptions(
            name="leadsource",
            options={"ordering": ["priority", "name"]},
        ),

        # ── NotificationWebhook ───────────────────────────────────────
        migrations.CreateModel(
            name="NotificationWebhook",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("kind", models.CharField(choices=[("slack", "Slack incoming webhook"), ("discord", "Discord webhook"), ("telegram", "Telegram bot (sendMessage)"), ("generic", "Generic JSON POST")], default="slack", max_length=20)),
                ("url", models.URLField(help_text="Slack/Discord: la URL di incoming webhook. Telegram: https://api.telegram.org/bot<TOKEN>/sendMessage. Generic: qualsiasi endpoint che accetta POST JSON.", verbose_name="Webhook URL")),
                ("telegram_chat_id", models.CharField(blank=True, help_text="Solo per Telegram — chat_id dove inviare il messaggio.", max_length=64, verbose_name="Telegram chat_id")),
                ("on_new_lead", models.BooleanField(default=True, verbose_name="Nuovo lead")),
                ("on_ftd", models.BooleanField(default=True, verbose_name="FTD")),
                ("on_sale_sold", models.BooleanField(default=True, verbose_name="Vendita venduta")),
                ("on_api_error", models.BooleanField(default=False, verbose_name="Errore API")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),

        # ── DispatchLog ───────────────────────────────────────────────
        migrations.CreateModel(
            name="DispatchLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_name", models.CharField(blank=True, help_text="Snapshot del nome al momento del dispatch.", max_length=120)),
                ("attempted_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("success", models.BooleanField(default=False)),
                ("response", models.JSONField(blank=True, default=dict)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("error", models.CharField(blank=True, max_length=255)),
                ("lead", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="dispatch_logs", to="leads.lead")),
                ("source", models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name="dispatch_logs", to="leads.leadsource")),
            ],
            options={"ordering": ["-attempted_at"]},
        ),

        # ── AutoMessage ───────────────────────────────────────────────
        migrations.CreateModel(
            name="AutoMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("trigger", models.CharField(choices=[("new_lead", "Nuovo lead"), ("ftd", "FTD")], default="new_lead", max_length=20)),
                ("subject", models.CharField(help_text="Variabili: {{firstname}}, {{lastname}}, {{email}}, {{country}}.", max_length=200)),
                ("body", models.TextField(help_text="Plain text. Variabili: {{firstname}}, {{lastname}}, {{email}}, {{phone}}, {{country}}, {{status}}.")),
                ("from_email", models.EmailField(blank=True, help_text="Vuoto = usa DEFAULT_FROM_EMAIL.", max_length=254)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["trigger", "name"]},
        ),
    ]
