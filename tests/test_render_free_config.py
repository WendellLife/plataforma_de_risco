"""Contrato do ambiente gratuito de demonstração no Render."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_blueprint_usa_somente_recursos_gratuitos_sem_worker() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "plan: free" in blueprint
    assert "plan: starter" not in blueprint
    assert "plan: basic-256mb" not in blueprint
    assert "type: worker" not in blueprint
    assert "CELERY_TASK_ALWAYS_EAGER" in blueprint


def test_producao_ativa_celery_eager_por_variavel_de_ambiente() -> None:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "CELERY_TASK_ALWAYS_EAGER": "1",
    }
    resultado = subprocess.run(
        [
            sys.executable,
            "-c",
            "from django.conf import settings; print(settings.CELERY_TASK_ALWAYS_EAGER)",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "True"
