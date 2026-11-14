"""Journal d'audit : qui a fait quoi, quand (écrit dans la transaction de l'action)."""
import json


def clean_detail(data):
    """Détail journalisable : jamais de mot de passe ni de hachage."""
    return {k: v for k, v in dict(data).items() if "password" not in k}


def log_event(ctx, action, entity, entity_id=None, detail=None) -> None:
    db = ctx.db
    if db is None:
        return
    user = ctx.session.user
    if detail is not None and not isinstance(detail, str):
        detail = json.dumps(detail, ensure_ascii=False, default=str)
    if detail and len(detail) > 1000:
        detail = detail[:1000]
    db.execute(
        "INSERT INTO audit_log(user_id, username, action, entity, entity_id, detail) "
        "VALUES(?,?,?,?,?,?)",
        (user.id if user else None, user.username if user else None,
         action, entity, entity_id, detail))
