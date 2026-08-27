import pytest
from decimal import Decimal

from ledger.family import FamilyError, FamilyService, PermissionDenied


@pytest.fixture
def service():
    return FamilyService(openid_resolver=lambda code: {"openid": "wx-" + code})


def setup_family(service):
    owner = service.wechat_login("owner", nickname="妈妈")
    member = service.wechat_login("member", nickname="爸爸")
    family = service.create_family(owner.id, "我们的家")
    return owner, member, family


def test_wechat_login_is_idempotent_and_updates_profile(service):
    first = service.wechat_login("same", nickname="初始昵称")
    second = service.wechat_login("same", nickname="新昵称")
    assert first.id == second.id
    assert second.openid == "wx-same"
    assert second.nickname == "新昵称"
    assert len(service.users) == 1


def test_create_family_adds_owner_member(service):
    owner = service.wechat_login("owner")
    family = service.create_family(owner.id, "家庭")
    members = [item for item in service.members.values() if item.family_id == family.id]
    assert family.owner_id == owner.id
    assert len(members) == 1
    assert members[0].role == "owner"


def test_only_owner_or_admin_can_invite(service):
    owner, member, family = setup_family(service)
    with pytest.raises(PermissionDenied):
        service.invite_member(member.id, family.id, owner.id)
    invited = service.invite_member(owner.id, family.id, member.id)
    assert invited.role == "member"
    assert service.list_families(member.id) == [family]


def test_invitation_token_can_only_be_accepted_once(service):
    owner, member, family = setup_family(service)
    invitation = service.create_invitation(owner.id, family.id, member.openid)
    accepted = service.accept_invitation(member.id, invitation.token)
    assert accepted.user_id == member.id
    assert invitation.status == "accepted"
    with pytest.raises(FamilyError):
        service.accept_invitation(member.id, invitation.token)


def test_account_visibility_and_public_account(service):
    owner, member, family = setup_family(service)
    service.invite_member(owner.id, family.id, member.id)
    private = service.create_account(owner.id, family.id, "支付宝", "alipay", owner_id=owner.id)
    public = service.create_account(owner.id, family.id, "家庭现金", "cash")
    visible = service.list_accounts(member.id, family.id)
    assert [item.id for item in visible] == [public.id]
    assert private.id not in {item.id for item in visible}


def test_member_cannot_create_account_and_invalid_type_rejected(service):
    owner, member, family = setup_family(service)
    service.invite_member(owner.id, family.id, member.id)
    with pytest.raises(PermissionDenied):
        service.create_account(member.id, family.id, "现金", "cash")
    with pytest.raises(FamilyError):
        service.create_account(owner.id, family.id, "未知", "crypto")


def test_owner_can_change_role_and_admin_can_only_disable_members(service):
    owner, member, family = setup_family(service)
    admin = service.wechat_login("admin")
    service.invite_member(owner.id, family.id, member.id)
    service.invite_member(owner.id, family.id, admin.id, role="admin")
    service.set_member_role(owner.id, family.id, member.id, "admin")
    with pytest.raises(PermissionDenied):
        service.disable_member(admin.id, family.id, member.id)
    service.set_member_role(owner.id, family.id, member.id, "member")
    disabled = service.disable_member(admin.id, family.id, member.id)
    assert disabled.status == "disabled"
    assert next(item for item in service.list_members(owner.id, family.id) if item.user_id == member.id).status == "disabled"


def test_account_can_be_edited_disabled_and_rejected_for_transactions(service):
    owner, member, family = setup_family(service)
    service.invite_member(owner.id, family.id, member.id)
    account = service.create_account(owner.id, family.id, "现金", "cash", initial_balance="12.345")
    assert account.initial_balance == Decimal("12.35")
    service.update_account(owner.id, family.id, account.id, name="家庭现金", owner_id=None)
    assert account.name == "家庭现金"
    assert account.owner_id is None
    service.disable_account(owner.id, family.id, account.id)
    assert account.status == "disabled"
    with pytest.raises(FamilyError):
        service.require_active_account(owner.id, family.id, account.id)
