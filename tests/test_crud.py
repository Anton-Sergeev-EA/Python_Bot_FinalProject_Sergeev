import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from database.crud import (
    create_ad,
    get_ad_by_id,
    get_ads_by_user,
    get_pending_ads,
    update_ad_status,
    delete_ad,
    search_ads,
    get_ads_count,
    get_user_by_id,
    create_user,
    update_user_contact,
    get_pending_ads_count,
)
from database.models import Ad, User, AdStatus
from database.session import SessionLocal
from config.settings import settings


class TestAdCRUD:

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()

        self.db.query(Ad).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.test_user = User(
            id=1001,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
        self.db.add(self.test_user)
        self.db.commit()

        yield

        self.db.query(Ad).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_create_ad_valid(self):
        ad_data = {
            "user_id": 1001,
            "text": "Test ad text",
            "contact_info": "test@example.com",
            "status": AdStatus.PENDING
        }

        ad = create_ad(**ad_data)

        assert ad is not None
        assert ad.id is not None
        assert ad.text == "Test ad text"
        assert ad.contact_info == "test@example.com"
        assert ad.status == AdStatus.PENDING
        assert ad.user_id == 1001

    def test_create_ad_invalid_user(self):
        ad_data = {
            "user_id": 999999,
            "text": "Test ad",
            "contact_info": "test@example.com"
        }

        with pytest.raises(IntegrityError):
            create_ad(**ad_data)

    def test_create_ad_empty_text(self):
        ad_data = {
            "user_id": 1001,
            "text": "",  # Empty text
            "contact_info": "test@example.com"
        }

        ad = create_ad(**ad_data)
        assert ad.text == ""

    def test_create_ad_long_text(self):
        long_text = "A" * 1000

        ad_data = {
            "user_id": 1001,
            "text": long_text,
            "contact_info": "test@example.com"
        }

        ad = create_ad(**ad_data)
        assert ad.text == long_text
        assert len(ad.text) == 1000

    def test_get_ad_by_id_existing(self):
        ad = create_ad(
            user_id=1001,
            text="Test ad",
            contact_info="test@example.com"
        )
        ad_id = ad.id

          retrieved_ad = get_ad_by_id(ad_id)

        assert retrieved_ad is not None
        assert retrieved_ad.id == ad_id
        assert retrieved_ad.text == "Test ad"

    def test_get_ad_by_id_nonexistent(self):
        ad = get_ad_by_id(999999)
        assert ad is None

    def test_get_ad_by_id_invalid(self):
        ad = get_ad_by_id(-1)
        assert ad is None

        ad = get_ad_by_id(0)
        assert ad is None

    def test_get_ads_by_user_existing(self):
        for i in range(3):
            create_ad(
                user_id=1001,
                text=f"Test ad {i}",
                contact_info=f"test{i}@example.com"
            )

        create_ad(
            user_id=1002,
            text="Other user ad",
            contact_info="other@example.com"
        )

        user_ads = get_ads_by_user(1001)

        assert len(user_ads) == 3
        for ad in user_ads:
            assert ad.user_id == 1001

    def test_get_ads_by_user_nonexistent(self):
        user_ads = get_ads_by_user(999999)
        assert len(user_ads) == 0

    def test_get_ads_by_user_no_ads(self):
        user_ads = get_ads_by_user(1001)  # User exists but has no ads
        assert len(user_ads) == 0

    def test_get_pending_ads(self):
        create_ad(user_id=1001, text="Pending 1", contact_info="test1@example.com", status=AdStatus.PENDING)
        create_ad(user_id=1001, text="Pending 2", contact_info="test2@example.com", status=AdStatus.PENDING)
        create_ad(user_id=1001, text="Approved", contact_info="test3@example.com", status=AdStatus.APPROVED)
        create_ad(user_id=1001, text="Rejected", contact_info="test4@example.com", status=AdStatus.REJECTED)

        pending_ads = get_pending_ads()

        assert len(pending_ads) == 2
        for ad in pending_ads:
            assert ad.status == AdStatus.PENDING

    def test_get_pending_ads_empty(self):
        create_ad(user_id=1001, text="Approved", contact_info="test@example.com", status=AdStatus.APPROVED)
        create_ad(user_id=1001, text="Rejected", contact_info="test@example.com", status=AdStatus.REJECTED)

        pending_ads = get_pending_ads()

        assert len(pending_ads) == 0

    def test_update_ad_status_existing(self):
        ad = create_ad(
            user_id=1001,
            text="Test ad",
            contact_info="test@example.com",
            status=AdStatus.PENDING
        )

        success = update_ad_status(ad.id, AdStatus.APPROVED)
        assert success is True

        updated_ad = get_ad_by_id(ad.id)
        assert updated_ad.status == AdStatus.APPROVED

    def test_update_ad_status_nonexistent(self):
        success = update_ad_status(999999, AdStatus.APPROVED)
        assert success is False

    def test_update_ad_status_same_status(self):
        ad = create_ad(
            user_id=1001,
            text="Test ad",
            contact_info="test@example.com",
            status=AdStatus.PENDING
        )

        success = update_ad_status(ad.id, AdStatus.PENDING)
        assert success is True  # Should succeed even if status is the same

    def test_update_ad_status_invalid_status(self):
        ad = create_ad(
            user_id=1001,
            text="Test ad",
            contact_info="test@example.com"
        )

        success = update_ad_status(ad.id, "INVALID_STATUS")

    def test_delete_ad_existing(self):
        ad = create_ad(
            user_id=1001,
            text="Test ad",
            contact_info="test@example.com"
        )
        ad_id = ad.id

        success = delete_ad(ad_id)
        assert success is True

        deleted_ad = get_ad_by_id(ad_id)
        assert deleted_ad is None

    def test_delete_ad_nonexistent(self):
        success = delete_ad(999999)
        assert success is False

    def test_delete_ad_already_deleted(self):
        ad = create_ad(
            user_id=1001,
            text="Test ad",
            contact_info="test@example.com"
        )
        ad_id = ad.id

        success1 = delete_ad(ad_id)
        assert success1 is True

        success2 = delete_ad(ad_id)
        assert success2 is False

    def test_search_ads_by_keyword(self):
        create_ad(user_id=1001, text="Selling iPhone 12", contact_info="test1@example.com", status=AdStatus.APPROVED)
        create_ad(user_id=1001, text="Buying MacBook Pro", contact_info="test2@example.com", status=AdStatus.APPROVED)
        create_ad(user_id=1001, text="iPhone case for sale", contact_info="test3@example.com", status=AdStatus.APPROVED)
        create_ad(user_id=1001, text="Android phone", contact_info="test4@example.com", status=AdStatus.APPROVED)

        results = search_ads("iPhone")
        assert len(results) == 2

        for ad in results:
            assert "iPhone" in ad.text

    def test_search_ads_empty_query(self):
        results = search_ads("")

    def test_search_ads_no_results(self):
        create_ad(user_id=1001, text="Selling laptop", contact_info="test@example.com", status=AdStatus.APPROVED)

        results = search_ads("nonexistentkeyword")
        assert len(results) == 0

    def test_search_ads_case_insensitive(self):
        create_ad(user_id=1001, text="Selling LAPTOP", contact_info="test@example.com", status=AdStatus.APPROVED)

        results_lower = search_ads("laptop")
        results_upper = search_ads("LAPTOP")

        assert len(results_lower) == 1
        assert len(results_upper) == 1

    def test_get_ads_count(self):
        for i in range(5):
            create_ad(
                user_id=1001,
                text=f"Ad {i}",
                contact_info=f"test{i}@example.com",
                status=AdStatus.APPROVED
            )

        count = get_ads_count()
        assert count >= 5

    def test_get_pending_ads_count(self):
        create_ad(user_id=1001, text="Pending 1", contact_info="test1@example.com", status=AdStatus.PENDING)
        create_ad(user_id=1001, text="Pending 2", contact_info="test2@example.com", status=AdStatus.PENDING)
        create_ad(user_id=1001, text="Approved", contact_info="test3@example.com", status=AdStatus.APPROVED)

        count = get_pending_ads_count()
        assert count == 2

    def test_get_pending_ads_count_empty(self):
        create_ad(user_id=1001, text="Approved", contact_info="test@example.com", status=AdStatus.APPROVED)
        create_ad(user_id=1001, text="Rejected", contact_info="test@example.com", status=AdStatus.REJECTED)

        count = get_pending_ads_count()
        assert count == 0


class TestUserCRUD:

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()

        self.db.query(User).delete()
        self.db.commit()

        yield

        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_create_user_valid(self):
        user_data = {
            "id": 2001,
            "username": "newuser",
            "first_name": "New",
            "last_name": "User"
        }

        user = create_user(**user_data)

        assert user is not None
        assert user.id == 2001
        assert user.username == "newuser"
        assert user.first_name == "New"

    def test_create_user_duplicate_id(self):
        create_user(id=3001, username="user1", first_name="First")

        with pytest.raises(IntegrityError):
            create_user(id=3001, username="user2", first_name="Second")

    def test_get_user_by_id_existing(self):
        user = create_user(id=4001, username="testuser", first_name="Test")

        retrieved_user = get_user_by_id(4001)

        assert retrieved_user is not None
        assert retrieved_user.id == 4001
        assert retrieved_user.username == "testuser"

    def test_get_user_by_id_nonexistent(self):
        user = get_user_by_id(999999)
        assert user is None

    def test_update_user_contact_existing(self):
        user = create_user(id=5001, username="user", first_name="Test")

        success = update_user_contact(5001, "new@example.com", "+1234567890")
        assert success is True

        updated_user = get_user_by_id(5001)
        assert updated_user.email == "new@example.com"
        assert updated_user.phone == "+1234567890"

    def test_update_user_contact_nonexistent(self):
        success = update_user_contact(999999, "test@example.com", "123456")
        assert success is False

    def test_update_user_contact_partial(self):
        user = create_user(id=6001, username="user", first_name="Test")

        success = update_user_contact(6001, "email@example.com", None)
        assert success is True

        updated_user = get_user_by_id(6001)
        assert updated_user.email == "email@example.com"
        assert updated_user.phone is None

        success = update_user_contact(6001, None, "+123456")
        assert success is True

        updated_user = get_user_by_id(6001)
        assert updated_user.email == "email@example.com"
        assert updated_user.phone == "+123456"
