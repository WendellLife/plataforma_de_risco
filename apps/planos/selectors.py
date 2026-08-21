"""Consultas do plano de ação. Sempre com escopo de tenant."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import QuerySet

from apps.ativos.models import Machine
from apps.clientes.models import Client
from motores.plano import Adequacao, calcular_adequacao, classificar_vencimento

from .enums import ActionStatus
from .models import Action


def acoes(*, machine: Machine | None = None, client: Client | None = None) -> QuerySet[Action]:
    qs = Action.objects.select_related(
        "plan", "plan__machine", "owner", "hazard", "item_result__library_item"
    ).prefetch_related("evidences", "deadline_changes")
    if machine is not None:
        qs = qs.filter(plan__machine=machine)
    if client is not None:
        qs = qs.filter(plan__machine__client=client)
    return qs


def linha_de_acao(action: Action, *, hoje: date | None = None) -> dict[str, Any]:
    vencimento = classificar_vencimento(
        prazo=action.deadline, concluida_em=action.completed_on,
        cancelada=action.status == ActionStatus.CANCELLED,
        iniciada=action.status == ActionStatus.IN_PROGRESS, hoje=hoje,
    )
    evidencias = list(action.evidences.all())
    return {
        "acao": action,
        "situacao": str(vencimento.situacao),
        "rotulo": vencimento.rotulo,
        "dias_restantes": vencimento.dias_restantes,
        "mensagem": vencimento.mensagem,
        "exige_atencao": vencimento.exige_atencao,
        "evidencias": evidencias,
        "sem_evidencia": not evidencias,
        "repactuacoes": action.deadline_changes.count(),
        "origem": action.origem_legivel,
    }


def _situacoes(qs: QuerySet[Action], hoje: date | None = None) -> list[str]:
    return [str(linha_de_acao(a, hoje=hoje)["situacao"]) for a in qs]


def adequacao(
    *, machine: Machine | None = None, client: Client | None = None, ate: date | None = None
) -> Adequacao:
    qs = acoes(machine=machine, client=client)
    lista = list(qs)
    return calcular_adequacao(
        [str(linha_de_acao(a)["situacao"]) for a in lista],
        concluidas_ate=[a.completed_on for a in lista],
        ate=ate,
    )


def curva_de_adequacao(
    *, client: Client, meses: int = 6, hoje: date | None = None
) -> list[dict[str, Any]]:
    """Evolução mês a mês pela DATA DO FATO — reconstrói o passado sem depender do lançamento."""
    fim = hoje or date.today()
    pontos: list[dict[str, Any]] = []
    for i in range(meses - 1, -1, -1):
        corte = _fim_do_mes(fim, -i)
        a = adequacao(client=client, ate=corte)
        pontos.append({
            "ate": corte, "percentual": a.percentual,
            "concluidas": a.concluidas, "total": a.total,
        })
    return pontos


def _fim_do_mes(referencia: date, delta_meses: int) -> date:
    mes = referencia.month + delta_meses
    ano = referencia.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    primeiro_do_seguinte = date(ano + (mes // 12), mes % 12 + 1, 1)
    return min(primeiro_do_seguinte - timedelta(days=1), referencia)


def indicadores(*, client: Client | None = None, hoje: date | None = None) -> dict[str, Any]:
    lista = [linha_de_acao(a, hoje=hoje) for a in acoes(client=client)]
    a = adequacao(client=client)
    return {
        "total": len(lista),
        "vencidas": sum(1 for l in lista if l["situacao"] == "vencida"),
        "a_vencer": sum(1 for l in lista if l["situacao"] == "a_vencer"),
        "concluidas": a.concluidas,
        "sem_evidencia": sum(
            1 for l in lista if l["sem_evidencia"] and l["situacao"] != "cancelada"
        ),
        "bloqueantes_abertas": sum(
            1 for l in lista
            if l["acao"].blocking and l["situacao"] not in ("concluida", "cancelada")
        ),
        "repactuadas": sum(1 for l in lista if l["repactuacoes"] > 0),
        "adequacao": a,
    }


def por_responsavel(*, client: Client | None = None, hoje: date | None = None) -> list[dict[str, Any]]:
    agrupado: dict[str, dict[str, Any]] = {}
    for l in [linha_de_acao(a, hoje=hoje) for a in acoes(client=client)]:
        nome = l["acao"].owner.name
        registro = agrupado.setdefault(
            nome, {"nome": nome, "total": 0, "vencidas": 0, "concluidas": 0}
        )
        registro["total"] += 1
        if l["situacao"] == "vencida":
            registro["vencidas"] += 1
        if l["situacao"] == "concluida":
            registro["concluidas"] += 1
    return sorted(agrupado.values(), key=lambda r: (-r["vencidas"], -r["total"]))


def acoes_bloqueantes_abertas(machine: Machine) -> list[Action]:
    """Insumo do verificador: ação bloqueante aberta retém a publicação do documento."""
    return [
        a for a in acoes(machine=machine).filter(blocking=True)
        if a.status not in (ActionStatus.DONE, ActionStatus.CANCELLED)
    ]
