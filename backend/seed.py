from database import SessionLocal
from models.ai_provider_config import AIProviderConfig


def seed_ai_providers(db):
    """
    Seeds default AI provider config rows.
    Only inserts if the table is empty — safe to call on every startup.
    """
    if db.query(AIProviderConfig).count() > 0:
        return  # Already seeded

    providers = [
        AIProviderConfig(
            provider_name="ollama",
            is_enabled=True,
            default_model="mistral:7b",
            module_overrides_json="{}",
            priority_order=1,
        ),
        AIProviderConfig(
            provider_name="claude",
            is_enabled=False,   # Disabled until API key is set
            default_model="claude-sonnet-4-6",
            module_overrides_json="{}",
            priority_order=2,
        ),
        AIProviderConfig(
            provider_name="openai",
            is_enabled=False,
            default_model="gpt-4o",
            module_overrides_json="{}",
            priority_order=3,
        ),
        AIProviderConfig(
            provider_name="gemini",
            is_enabled=False,
            default_model="gemini-1.5-pro",
            module_overrides_json="{}",
            priority_order=4,
        ),
    ]

    db.add_all(providers)
    db.commit()
    print("✅ AI providers seeded.")


if __name__ == "__main__":
    db = SessionLocal()
    seed_ai_providers(db)
    db.close()
