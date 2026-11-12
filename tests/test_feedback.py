import importlib
import os
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

original_database_url = os.environ.get("DATABASE_URL")
original_deepl_api_key = os.environ.get("DEEPL_API_KEY")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPL_API_KEY"] = "test-key"

api_module = importlib.import_module("backend.api")
database_module = importlib.import_module("backend.database")
models_module = importlib.import_module("backend.models")

if original_database_url is None:
    os.environ.pop("DATABASE_URL", None)
else:
    os.environ["DATABASE_URL"] = original_database_url

if original_deepl_api_key is None:
    os.environ.pop("DEEPL_API_KEY", None)
else:
    os.environ["DEEPL_API_KEY"] = original_deepl_api_key

app = api_module.app
Base = database_module.Base
get_db = database_module.get_db
FeedbackAttachment = models_module.FeedbackAttachment
FeedbackMessage = models_module.FeedbackMessage


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


class FeedbackEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        with TestSessionLocal() as db:
            db.query(FeedbackAttachment).delete()
            db.query(FeedbackMessage).delete()
            db.commit()

    def test_saves_feedback_message(self):
        response = self.client.post(
            "/feedback",
            data={"message": "  Very helpful  "}
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "received")
        with TestSessionLocal() as db:
            saved_feedback = db.query(FeedbackMessage).one()
            self.assertEqual(saved_feedback.message, "Very helpful")

    def test_rejects_empty_feedback(self):
        response = self.client.post(
            "/feedback",
            json={"message": "   "}
        )

        self.assertEqual(response.status_code, 422)
        with TestSessionLocal() as db:
            self.assertEqual(db.query(FeedbackMessage).count(), 0)

    def test_rejects_feedback_over_limit(self):
        response = self.client.post(
            "/feedback",
            data={"message": "x" * 1001}
        )

        self.assertEqual(response.status_code, 422)
        with TestSessionLocal() as db:
            self.assertEqual(db.query(FeedbackMessage).count(), 0)

    def test_saves_optional_screenshot(self):
        screenshot_data = b"\x89PNG\r\n\x1a\nfeedback screenshot"
        response = self.client.post(
            "/feedback",
            data={"message": "The button is hard to find"},
            files={
                "screenshot": (
                    "feedback.png",
                    screenshot_data,
                    "image/png"
                )
            }
        )

        self.assertEqual(response.status_code, 201)
        with TestSessionLocal() as db:
            attachment = db.query(FeedbackAttachment).one()
            self.assertEqual(
                attachment.feedback_id,
                response.json()["id"]
            )
            self.assertEqual(attachment.data, screenshot_data)



if __name__ == "__main__":
    unittest.main()
