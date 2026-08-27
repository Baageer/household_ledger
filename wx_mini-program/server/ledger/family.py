"""M1 家庭基础领域服务：微信身份、家庭成员和账户权限。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable, Dict, List, Optional
from uuid import uuid4

ROLES = ("owner", "admin", "member")
ACCOUNT_TYPES = ("cash", "bank", "alipay", "wechat", "credit_card", "other")
_UNSET = object()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class User:
    id: str
    openid: str
    unionid: Optional[str] = None
    nickname: str = ""
    avatar: str = ""
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@dataclass
class Family:
    id: str
    name: str
    owner_id: str
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@dataclass
class FamilyMember:
    id: str
    family_id: str
    user_id: str
    role: str
    nickname: str = ""
    status: str = "active"
    created_at: datetime = field(default_factory=_now)


@dataclass
class Account:
    id: str
    family_id: str
    owner_id: Optional[str]
    name: str
    type: str
    currency: str = "CNY"
    initial_balance: Decimal = Decimal("0.00")
    status: str = "active"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@dataclass
class Invitation:
    token: str
    family_id: str
    inviter_id: str
    invitee_openid: str
    role: str = "member"
    status: str = "pending"
    created_at: datetime = field(default_factory=_now)


class FamilyError(ValueError):
    """家庭业务参数或状态无效。"""


class AuthenticationError(FamilyError):
    """用户身份无法解析。"""


class PermissionDenied(FamilyError):
    """当前成员没有执行操作的权限。"""


class FamilyService:
    """进程内 M1 服务；通过 ``openid_resolver`` 接入微信 code2Session。"""

    def __init__(self, openid_resolver: Optional[Callable[[str], object]] = None):
        self.users: Dict[str, User] = {}
        self.users_by_openid: Dict[str, str] = {}
        self.families: Dict[str, Family] = {}
        self.members: Dict[str, FamilyMember] = {}
        self.accounts: Dict[str, Account] = {}
        self.invitations: Dict[str, Invitation] = {}
        self._openid_resolver = openid_resolver or (lambda code: {"openid": code})

    def wechat_login(self, code: str, nickname: str = "", avatar: str = "") -> User:
        if not code or not code.strip():
            raise AuthenticationError("微信登录 code 不能为空")
        response = self._openid_resolver(code)
        if isinstance(response, str):
            openid, unionid = response, None
        else:
            openid = response.get("openid") if response else None
            unionid = response.get("unionid") if response else None
        if not openid:
            raise AuthenticationError("微信登录未返回 openid")
        if openid in self.users_by_openid:
            user = self.users[self.users_by_openid[openid]]
            user.nickname = nickname or user.nickname
            user.avatar = avatar or user.avatar
            user.unionid = unionid or user.unionid
            user.updated_at = _now()
            return user
        user = User(_id("usr"), openid, unionid, nickname, avatar)
        self.users[user.id] = user
        self.users_by_openid[openid] = user.id
        return user

    def create_family(self, user_id: str, name: str) -> Family:
        self._require_user(user_id)
        if not name or not name.strip():
            raise FamilyError("家庭名称不能为空")
        family = Family(_id("fam"), name.strip(), user_id)
        self.families[family.id] = family
        self._add_member(family.id, user_id, "owner")
        return family

    def list_families(self, user_id: str) -> List[Family]:
        self._require_user(user_id)
        ids = {m.family_id for m in self.members.values() if m.user_id == user_id and m.status == "active"}
        return sorted((self.families[i] for i in ids), key=lambda item: item.created_at)

    def list_members(self, actor_user_id: str, family_id: str) -> List[FamilyMember]:
        self._require_member(actor_user_id, family_id)
        return [m for m in self.members.values() if m.family_id == family_id]

    def invite_member(self, actor_user_id: str, family_id: str, invitee_user_id: str, role: str = "member", nickname: str = "") -> FamilyMember:
        if role not in ("admin", "member"):
            raise FamilyError("邀请成员角色只能是 admin 或 member")
        actor = self._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以邀请成员")
        self._require_user(invitee_user_id)
        existing = self._find_member(family_id, invitee_user_id)
        if existing:
            existing.status = "active"
            return existing
        return self._add_member(family_id, invitee_user_id, role, nickname)

    def create_invitation(self, actor_user_id: str, family_id: str, invitee_openid: str, role: str = "member") -> Invitation:
        if role not in ("admin", "member"):
            raise FamilyError("邀请成员角色只能是 admin 或 member")
        actor = self._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以邀请成员")
        if not invitee_openid or not invitee_openid.strip():
            raise FamilyError("邀请对象不能为空")
        invitation = Invitation(_id("inv"), family_id, actor_user_id, invitee_openid.strip(), role)
        self.invitations[invitation.token] = invitation
        return invitation

    def accept_invitation(self, user_id: str, token: str) -> FamilyMember:
        user = self._require_user(user_id)
        invitation = self.invitations.get(token)
        if not invitation or invitation.status != "pending":
            raise FamilyError("邀请不存在或已处理")
        if user.openid != invitation.invitee_openid:
            raise PermissionDenied("该邀请不属于当前微信用户")
        member = self.invite_member(invitation.inviter_id, invitation.family_id, user_id, invitation.role)
        invitation.status = "accepted"
        return member

    def set_member_role(self, actor_user_id: str, family_id: str, member_user_id: str, role: str) -> FamilyMember:
        if role not in ROLES:
            raise FamilyError("无效的家庭角色")
        actor = self._require_member(actor_user_id, family_id)
        if actor.role != "owner":
            raise PermissionDenied("只有 owner 可以修改成员角色")
        member = self._require_member(member_user_id, family_id)
        if member.user_id == self.families[family_id].owner_id and role != "owner":
            raise FamilyError("不能降级家庭 owner")
        if role == "owner":
            old_owner = self._require_member(self.families[family_id].owner_id, family_id)
            old_owner.role = "admin"
            self.families[family_id].owner_id = member.user_id
        member.role = role
        return member

    def disable_member(self, actor_user_id: str, family_id: str, member_user_id: str) -> FamilyMember:
        actor = self._require_member(actor_user_id, family_id)
        target = self._require_member(member_user_id, family_id)
        if target.user_id == self.families[family_id].owner_id:
            raise FamilyError("不能禁用家庭 owner")
        if actor.user_id == target.user_id:
            raise FamilyError("不能禁用自己")
        if actor.role == "admin" and target.role != "member":
            raise PermissionDenied("admin 只能禁用普通成员")
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以禁用成员")
        target.status = "disabled"
        return target

    def create_account(self, actor_user_id: str, family_id: str, name: str, account_type: str, owner_id: Optional[str] = None, currency: str = "CNY", initial_balance: float = 0.0) -> Account:
        actor = self._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以管理账户")
        if account_type not in ACCOUNT_TYPES:
            raise FamilyError("无效的账户类型")
        if not name or not name.strip():
            raise FamilyError("账户名称不能为空")
        if owner_id is not None:
            self._require_member(owner_id, family_id)
        if not currency or not currency.strip():
            raise FamilyError("账户币种不能为空")
        try:
            balance = Decimal(str(initial_balance)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            raise FamilyError("初始余额必须是有效金额")
        account = Account(_id("acct"), family_id, owner_id, name.strip(), account_type, currency.upper(), balance)
        self.accounts[account.id] = account
        return account

    def update_account(
        self,
        actor_user_id: str,
        family_id: str,
        account_id: str,
        name: Optional[str] = None,
        owner_id: object = _UNSET,
        currency: Optional[str] = None,
    ) -> Account:
        actor = self._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以编辑账户")
        account = self._require_account(account_id, family_id)
        if name is not None:
            if not name.strip():
                raise FamilyError("账户名称不能为空")
            account.name = name.strip()
        if owner_id is not _UNSET:
            if owner_id is not None:
                self._require_member(str(owner_id), family_id)
            account.owner_id = owner_id
        if currency is not None:
            if not currency.strip():
                raise FamilyError("账户币种不能为空")
            account.currency = currency.upper()
        account.updated_at = _now()
        return account

    def disable_account(self, actor_user_id: str, family_id: str, account_id: str) -> Account:
        actor = self._require_member(actor_user_id, family_id)
        if actor.role not in ("owner", "admin"):
            raise PermissionDenied("只有 owner 或 admin 可以停用账户")
        account = self._require_account(account_id, family_id)
        account.status = "disabled"
        account.updated_at = _now()
        return account

    def require_active_account(self, actor_user_id: str, family_id: str, account_id: str) -> Account:
        self._require_member(actor_user_id, family_id)
        account = self._require_account(account_id, family_id)
        if account.status != "active":
            raise FamilyError("停用账户不可新增交易")
        return account

    def list_accounts(self, actor_user_id: str, family_id: str) -> List[Account]:
        actor = self._require_member(actor_user_id, family_id)
        accounts = [a for a in self.accounts.values() if a.family_id == family_id]
        return accounts if actor.role in ("owner", "admin") else [a for a in accounts if a.owner_id in (None, actor_user_id)]

    def _require_account(self, account_id: str, family_id: str) -> Account:
        account = self.accounts.get(account_id)
        if not account or account.family_id != family_id:
            raise FamilyError("账户不存在")
        return account

    def _require_user(self, user_id: str) -> User:
        if user_id not in self.users:
            raise AuthenticationError("用户不存在")
        return self.users[user_id]

    def _require_member(self, user_id: str, family_id: str) -> FamilyMember:
        if family_id not in self.families:
            raise FamilyError("家庭不存在")
        member = self._find_member(family_id, user_id)
        if not member or member.status != "active":
            raise PermissionDenied("用户不是该家庭的有效成员")
        return member

    def _find_member(self, family_id: str, user_id: str) -> Optional[FamilyMember]:
        return next((m for m in self.members.values() if m.family_id == family_id and m.user_id == user_id), None)

    def _add_member(self, family_id: str, user_id: str, role: str, nickname: str = "") -> FamilyMember:
        member = FamilyMember(_id("mem"), family_id, user_id, role, nickname)
        self.members[member.id] = member
        return member
