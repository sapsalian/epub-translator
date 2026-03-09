"""Integration tests for API routes."""

import io

import pytest

from src.pipeline.models import Language
from src.pipeline.persistence import CheckpointManager, FilePersistenceBackend
from src.pipeline.models import PreprocessResult, TermDictionary
from src.app.jobs.models import JobState


class TestHealthRoute:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestLanguagesRoute:
    @pytest.mark.asyncio
    async def test_list_languages(self, client):
        resp = await client.get("/api/languages")
        assert resp.status_code == 200
        data = resp.json()
        codes = {lang["code"] for lang in data["languages"]}
        expected_codes = {lang.value for lang in Language}
        assert codes == expected_codes

    @pytest.mark.asyncio
    async def test_languages_have_labels(self, client):
        resp = await client.get("/api/languages")
        for lang in resp.json()["languages"]:
            assert "code" in lang
            assert "label" in lang
            assert isinstance(lang["label"], str)


class TestSettingsRoute:
    @pytest.mark.asyncio
    async def test_get_default_settings(self, client):
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "gpt-4.1-mini"
        assert data["api_key_set"] is False
        assert "openai_api_key" not in data

    @pytest.mark.asyncio
    async def test_put_settings(self, client):
        resp = await client.put("/api/settings", json={"model": "gpt-4o"})
        assert resp.status_code == 200
        assert resp.json()["model"] == "gpt-4o"

        resp = await client.get("/api/settings")
        assert resp.json()["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_put_api_key_sets_flag(self, client):
        resp = await client.put("/api/settings", json={"openai_api_key": "sk-test"})
        assert resp.status_code == 200
        assert resp.json()["api_key_set"] is True
        assert "openai_api_key" not in resp.json()


class TestUploadRoute:
    @pytest.mark.asyncio
    async def test_upload_epub(self, client):
        content = b"PK\x03\x04fake epub content"
        files = {"file": ("test.epub", io.BytesIO(content), "application/epub+zip")}
        resp = await client.post("/api/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "upload_id" in data
        assert data["filename"] == "test.epub"
        assert len(data["upload_id"]) > 0

    @pytest.mark.asyncio
    async def test_upload_non_epub_rejected(self, client):
        files = {"file": ("readme.txt", io.BytesIO(b"hello"), "text/plain")}
        resp = await client.post("/api/upload", files=files)
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestJobsRoute:
    async def _upload_epub(self, client):
        content = b"PK\x03\x04fake epub"
        files = {"file": ("book.epub", io.BytesIO(content), "application/epub+zip")}
        resp = await client.post("/api/upload", files=files)
        return resp.json()["upload_id"]

    @pytest.mark.asyncio
    async def test_create_job(self, client):
        upload_id = await self._upload_epub(client)
        resp = await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
        })
        assert resp.status_code == 200
        assert "job_id" in resp.json()

    @pytest.mark.asyncio
    async def test_create_job_with_workflow_mode(self, client):
        upload_id = await self._upload_epub(client)
        resp = await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
            "workflow_mode": "glossary_review",
            "workflow_options": {"draft": True},
        })
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        detail = await client.get(f"/api/jobs/{job_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["workflow_mode"] == "glossary_review"
        assert data["workflow_options"] == {"draft": True}

    @pytest.mark.asyncio
    async def test_create_job_invalid_upload(self, client):
        resp = await client.post("/api/jobs", json={
            "upload_id": "nonexistent",
            "source_language": "en",
            "target_language": "ko",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_jobs(self, client):
        upload_id = await self._upload_epub(client)
        await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
        })

        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) >= 1
        assert jobs[0]["filename"] == "book.epub"

    @pytest.mark.asyncio
    async def test_get_job_detail(self, client):
        upload_id = await self._upload_epub(client)
        create_resp = await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
        })
        job_id = create_resp.json()["job_id"]

        resp = await client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert "queue_position" in data
        assert data["state"] == "queued"
        assert data["workflow_mode"] == "classic"
        assert data["workflow_options"] == {}

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, client):
        resp = await client.get("/api/jobs/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_job(self, client):
        upload_id = await self._upload_epub(client)
        create_resp = await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
        })
        job_id = create_resp.json()["job_id"]

        resp = await client.delete(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        resp = await client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self, client):
        resp = await client.delete("/api/jobs/nonexistent")
        assert resp.status_code == 404

    async def _seed_glossary_checkpoint(self, test_app, job_id: str, epub_id: str, target_language: str):
        checkpoint_path = test_app.state.config.checkpoint_dir / job_id
        backend = FilePersistenceBackend(str(checkpoint_path))
        await backend.initialize()
        manager = CheckpointManager(backend)
        preprocess = PreprocessResult(
            epub_id=epub_id,
            term_dictionary=TermDictionary(
                source_language=Language.ENGLISH,
                target_language=Language(target_language),
                mappings={"Hellhounds": "헬하운드", "Milo": "마일로"},
            ),
            summaries={},
            epub_summary="",
        )
        await manager.save_preprocess(preprocess, target_language)

    @pytest.mark.asyncio
    async def test_get_job_glossary(self, client, test_app):
        upload_id = await self._upload_epub(client)
        create_resp = await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
            "workflow_mode": "glossary_review",
        })
        job_id = create_resp.json()["job_id"]

        manager = test_app.state.job_manager
        job = manager.get_job(job_id)
        assert job is not None
        job.state = JobState.AWAITING_REVIEW
        job.epub_id = "epub-123"
        manager.save()
        await self._seed_glossary_checkpoint(test_app, job_id, "epub-123", "ko")

        resp = await client.get(f"/api/jobs/{job_id}/glossary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_edits"] is False
        assert any(item["source"] == "Hellhounds" for item in data["terms"])

    @pytest.mark.asyncio
    async def test_put_job_glossary_and_continue(self, client, test_app):
        upload_id = await self._upload_epub(client)
        create_resp = await client.post("/api/jobs", json={
            "upload_id": upload_id,
            "source_language": "en",
            "target_language": "ko",
            "workflow_mode": "glossary_review",
        })
        job_id = create_resp.json()["job_id"]

        manager = test_app.state.job_manager
        job = manager.get_job(job_id)
        assert job is not None
        job.state = JobState.AWAITING_REVIEW
        job.epub_id = "epub-123"
        manager.save()
        await self._seed_glossary_checkpoint(test_app, job_id, "epub-123", "ko")

        put_resp = await client.put(
            f"/api/jobs/{job_id}/glossary",
            json={"terms": [{"source": "Milo", "target": "밀로"}]},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["ok"] is True

        get_resp = await client.get(f"/api/jobs/{job_id}/glossary")
        assert get_resp.status_code == 200
        assert get_resp.json()["has_edits"] is True
        assert get_resp.json()["terms"] == [{"source": "Milo", "target": "밀로"}]

        cont_resp = await client.post(f"/api/jobs/{job_id}/continue")
        assert cont_resp.status_code == 200
        assert cont_resp.json()["ok"] is True
        updated = manager.get_job(job_id)
        assert updated is not None
        assert updated.state.value == "queued"
        assert updated.workflow_options.get("review_approved") is True


class TestDownloadRoute:
    @pytest.mark.asyncio
    async def test_download_invalid_token(self, client):
        resp = await client.get("/download/bad-token")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_download_valid_token(self, client, test_app, tmp_path):
        epub_file = tmp_path / "translated.epub"
        epub_file.write_bytes(b"PK\x03\x04epub content")

        manager = test_app.state.job_manager
        token = manager.register_download(epub_file)

        resp = await client.get(f"/download/{token}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/epub+zip"

    @pytest.mark.asyncio
    async def test_download_file_gone(self, client, test_app, tmp_path):
        epub_file = tmp_path / "gone.epub"
        epub_file.write_bytes(b"temp")

        manager = test_app.state.job_manager
        token = manager.register_download(epub_file)

        epub_file.unlink()
        resp = await client.get(f"/download/{token}")
        assert resp.status_code == 410
