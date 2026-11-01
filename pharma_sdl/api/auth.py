"""المصادقة والأدوار (RBAC) — هوية بشرية لكل ترقية اعتماد (P2، تقييم #5).

النموذج: مفاتيح API من البيئة فقط (`PHARMA_SDL_API_KEYS`) بصيغة:

    PHARMA_SDL_API_KEYS="lab-admin:sk-...:admin,batch:sk-...:scientist,read:sk-...:viewer"

    - تُجزَّأ المفاتيح sha256 عند التحميل — لا نص صريح في الذاكرة أو السجلات.
    - ثلاثة أدوار صارمة: viewer < scientist < admin.
      viewer    قراءة كل شيء: أهداف، محركات، نتائج، تقارير، تجارب، بطاقات اعتماد
      scientist + إطلاق الفرز والفحوص المخبرية
      admin     + ترقية/تخفيض حالة الاعتماد (البوابة البشرية — لا أحد أقل يلمسها)
    - الوضع المفتوح (بلا مفاتيح مُعدّة): التطوير المحلي يعمل كما كان — كل طلب
      يُعامل admin، و`/health` يصرّح `auth_mode: "open"`. النشر العام يستوجب مفاتيح.

النقاط المفتوحة دوماً (بلا مفتاح) — حصراً: `/`، `/api/v1/health`،
`/api/v1/version` — لأن فحوص الحاويات والمراقبة تعتمدها ولا تكشف شيئاً.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from fastapi import Header

from pharma_sdl.errors import ForbiddenError, UnauthorizedError, ValidationError


class Role(str, Enum):
    """الأدوار الثلاثة — الترتيب صارم والصعود بضوء أخضر صريح من المشغّل."""

    VIEWER = "viewer"
    SCIENTIST = "scientist"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK: dict[Role, int] = {Role.VIEWER: 0, Role.SCIENTIST: 1, Role.ADMIN: 2}


@dataclass(frozen=True)
class Principal:
    """من يتكلم مع الـAPI — معرّف المفتاح ودوره (لا المفتاح نفسه أبداً)."""

    key_id: str
    role: Role

    def public(self) -> dict[str, str]:
        """تمثيل آمن للعرض — لا يجوز أن يصل المفتاح الخام هنا أبداً."""
        return {"key_id": self.key_id, "role": self.role.value}


_ANONYMOUS = Principal(key_id="anonymous", role=Role.ADMIN)


def hash_key(raw: str) -> str:
    """sha256 hex للمفتاح — الصيغة المخزنة والمقارنة عليها حصراً."""
    return hashlib.sha256(raw.strip().encode()).hexdigest()


def parse_api_keys(raw: str) -> dict[str, Principal]:
    """تفكيك سلسلة المفاتيح إلى خريطة sha256 → Principal.

    صارم بصدق: إدخال مشوه يُسقط الإقلاع (ValidationError) بدل أن يفتح
    باباً بلا دور أو يبصر بصمت — المصادقة النصفية أخطر من غيابها.
    """
    principals: dict[str, Principal] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) != 3 or not parts[0].strip() or not parts[1].strip():
            raise ValidationError(
                "مفتاح API مشوه — الصيغة المطلوبة: id:key:role (id,key,role غير فارغة)",
                "Malformed API key — expected id:key:role with non-empty parts",
            )
        key_id, secret, role_raw = parts
        try:
            role = Role(role_raw.strip().lower())
        except ValueError as exc:
            raise ValidationError(
                f"دور غير معروف للمفتاح {key_id}: {role_raw} — الأدوار: viewer/scientist/admin",
                f"Unknown role for key {key_id}: {role_raw} — roles: viewer/scientist/admin",
            ) from exc
        digest = hash_key(secret)
        if digest in principals:
            raise ValidationError(
                f"مفتاح مكرر بصمة: {key_id}", f"Duplicate key digest: {key_id}"
            )
        principals[digest] = Principal(key_id=key_id.strip(), role=role)
    return principals


def auth_enabled() -> bool:
    """هل المصادقة مفعلة؟ (توجد مفاتيح مُعدّة في البيئة)"""
    from pharma_sdl.api.deps import app_settings

    return bool(app_settings().api_keys.strip())


def resolve_principal(x_api_key: str | None) -> Principal:
    """حسم الهوية من ترويسة الطلب — الوضع المفتوح يعطي admin صريح الإعلان."""
    from pharma_sdl.api.deps import app_settings

    raw = app_settings().api_keys
    if not raw.strip():
        return _ANONYMOUS
    if not x_api_key:
        raise UnauthorizedError(
            "ترويسة X-API-Key مفقودة — المصادقة مفعلة على هذه النسخة",
            "X-API-Key header missing — authentication is enforced on this deployment",
        )
    principal = parse_api_keys(raw).get(hash_key(x_api_key))
    if principal is None:
        raise UnauthorizedError(
            "مفتاح API غير معروف — راسل مشغّل المنصة للحصول على مفتاح بدور مناسب",
            "Unknown API key — ask the platform operator for a key with the right role",
        )
    return principal


def require_role(minimum: Role):
    """مصنع تبعية FastAPI — يرفض أدنى من الدور المطلوب برفض صادق 403."""

    def _dependency(x_api_key: str | None = Header(default=None)) -> Principal:
        principal = resolve_principal(x_api_key)
        if principal.role.rank < minimum.rank:
            raise ForbiddenError(
                f"الدور {principal.role.value} أدنى من المطلوب {minimum.value} — "
                "هذه العملية لا تُنفَّذ بأدنى من الدور المطلوب",
                f"Role '{principal.role.value}' is below required '{minimum.value}' — "
                "this operation is not permitted for lower roles",
            )
        return principal

    return _dependency


def auth_mode_label() -> str:
    """وضع المصادقة للعرض في /health — صادق دائماً."""
    return "enforced" if auth_enabled() else "open"


__all__ = [
    "Principal",
    "Role",
    "auth_enabled",
    "auth_mode_label",
    "hash_key",
    "parse_api_keys",
    "require_role",
    "resolve_principal",
]
