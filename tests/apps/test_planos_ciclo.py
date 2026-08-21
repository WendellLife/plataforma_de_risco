"""Ciclo achado → correção com banco (CA-08).

O que estes testes garantem é a regra central do plano: não se encerra ação sem prova, e
o percentual de adequação conta pela data do fato.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.ativos.models import Machine, Project
from apps.checklists.enums import ItemResult, Standard
from apps.checklists.models import LibraryItem
from apps.checklists.services import abrir_aplicacao, responder_item
from apps.clientes.enums import PersonRole
from apps.clientes.models import Person
from apps.clientes.services import criar_cliente
from apps.core.enums import AuditAction
from apps.core.models import AuditLog, Tenant
from apps.planos.enums import ActionSource, ActionStatus
from apps.planos.models import Action, ActionPlan
from apps.planos.selectors import (
    acoes_bloqueantes_abertas,
    adequacao,
    curva_de_adequacao,
    indicadores,
    linha_de_acao,
)
from apps.planos.services import (
    AcaoJaEncerrada,
    EncerramentoSemEvidencia,
    PrazoSemJustificativa,
    abrir_plano,
    anexar_evidencia,
    cancelar_acao,
    concluir_acao,
    criar_acao,
    gerar_acoes_de_nao_conformidade,
    repactuar_prazo,
)
from apps.risco.enums import EstimateKind, Iso12100Step, Iso12100Type
from apps.risco.models import Hazard
from apps.risco.services import propor_medida, registrar_estimativa

pytestmark = pytest.mark.django_db


@pytest.fixture
def responsavel(tenant_a: Tenant, escopo_a: None) -> Person:
    return Person.objects.create(
        tenant=tenant_a, name="Jonas Ribeiro", doc_kind="cpf", doc_number="99988877766",
        roles=[PersonRole.RESPONSIBLE],
    )


@pytest.fixture
def maquina(tenant_a: Tenant, escopo_a: None, engenheiro_a) -> Machine:  # noqa: ANN001
    cliente = criar_cliente(
        legal_name="Cartonagem Teste", tax_id="66666666000166", actor=engenheiro_a
    )
    eng = Person.objects.create(
        tenant=tenant_a, name="Wendell Engenheiro", doc_kind="cpf", doc_number="11122233344",
        roles=[PersonRole.ENGINEER], council="CREA", council_state="SP",
        council_number="5069123456", professional_title="Engenheiro de Segurança do Trabalho",
    )
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number="PL-1-001", engineer=eng, status="active"
    )
    return Machine.objects.create(
        tenant=tenant_a, client=cliente, project=projeto, name="12 - Onduladeira"
    )


@pytest.fixture
def perigo_com_medida(maquina: Machine, tenant_a: Tenant, engenheiro_a, escopo_a) -> Hazard:  # noqa: ANN001
    p = Hazard.objects.create(
        tenant=tenant_a, machine=maquina, zone="Zona de corte transversal",
        title="Contato com faca rotativa", iso12100_type=Iso12100Type.MECHANICAL,
    )
    registrar_estimativa(
        hazard=p, kind=EstimateKind.INITIAL, lo=Decimal("5"), fe=Decimal("2.5"),
        dph=Decimal("15"), np=Decimal("2"), actor=engenheiro_a,
    )
    propor_medida(
        hazard=p, iso12100_step=Iso12100Step.SAFEGUARDING,
        text="Instalar proteção fixa com interbloqueio na zona de corte.", actor=engenheiro_a,
    )
    return p


# --------------------------------------------------------------------------- geração

def test_um_plano_por_maquina(maquina: Machine, engenheiro_a, escopo_a) -> None:  # noqa: ANN001
    primeiro = abrir_plano(machine=maquina, actor=engenheiro_a)
    segundo = abrir_plano(machine=maquina, actor=engenheiro_a)
    assert primeiro.pk == segundo.pk
    assert ActionPlan.objects.filter(machine=maquina).count() == 1


def test_achado_gera_acao_com_responsavel_e_prazo(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    criadas = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)
    assert len(criadas) == 1
    acao = criadas[0]
    assert acao.owner is not None          # nunca "a definir"
    assert acao.deadline is not None
    assert acao.source == ActionSource.RECOMMENDATION
    # Não bloqueante: ver test_geracao_nao_cria_impasse_circular.
    assert acao.blocking is False


def test_prazo_da_acao_vem_da_faixa_de_hrn(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """HRN 375 é faixa 'muito alto' → 20 dias, não um número redondo qualquer."""
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    assert acao.suggested_days == 20
    assert acao.deadline == timezone.localdate() + timedelta(days=20)


def test_regerar_nao_duplica(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)
    segunda = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)
    assert segunda == []
    assert Action.objects.filter(plan__machine=maquina).count() == 1


def test_item_de_checklist_nao_conforme_tambem_gera_acao(
    maquina: Machine, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    item = LibraryItem.objects.create(
        library_key="NR12-101", standard=Standard.NR12, statement="Proteção fixa na transmissão."
    )
    aplicacao = abrir_aplicacao(
        machine_id=maquina.pk, standard=Standard.NR12, actor=engenheiro_a
    )
    responder_item(
        assessment=aplicacao, library_key=item.library_key,
        result=ItemResult.NON_COMPLIANT, actor=engenheiro_a,
    )
    criadas = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)
    assert len(criadas) == 1
    assert criadas[0].source == ActionSource.CHECKLIST


def test_sem_responsavel_possivel_recusa_em_vez_de_inventar(
    tenant_a: Tenant, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    cliente = criar_cliente(legal_name="Sem Eng", tax_id="10101010000110", actor=engenheiro_a)
    m = Machine.objects.create(tenant=tenant_a, client=cliente, name="Sem projeto")
    with pytest.raises(ValueError, match="responsável nominal"):
        gerar_acoes_de_nao_conformidade(machine=m, actor=engenheiro_a)


# ------------------------------------------------------------------ evidência e fecho

def test_nao_encerra_sem_evidencia(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    with pytest.raises(EncerramentoSemEvidencia, match="sem evidência"):
        concluir_acao(action=acao, actor=engenheiro_a)
    acao.refresh_from_db()
    assert acao.status == ActionStatus.OPEN
    assert acao.completed_on is None


def test_encerra_com_evidencia_e_grava_a_data_do_fato(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """A data do fato é a da evidência, não a de hoje."""
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    anexar_evidencia(
        action=acao, file_key="campo/1/protecao.jpg", caption="Proteção instalada",
        occurred_on=date(2026, 7, 15), actor=engenheiro_a,
    )
    concluir_acao(action=acao, actor=engenheiro_a)
    acao.refresh_from_db()
    assert acao.status == ActionStatus.DONE
    assert acao.completed_on == date(2026, 7, 15)


def test_acao_encerrada_nao_volta_a_ser_editada(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    anexar_evidencia(action=acao, file_key="campo/1/a.jpg", actor=engenheiro_a)
    concluir_acao(action=acao, actor=engenheiro_a)
    with pytest.raises(AcaoJaEncerrada):
        repactuar_prazo(
            action=acao, novo_prazo=date(2026, 12, 1), reason="tentativa", actor=engenheiro_a
        )


def test_cancelamento_exige_motivo(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    with pytest.raises(ValueError, match="motivo"):
        cancelar_acao(action=acao, reason="   ", actor=engenheiro_a)


# ------------------------------------------------------------------------- repactuação

def test_repactuar_sem_justificativa_e_recusado(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    with pytest.raises(PrazoSemJustificativa):
        repactuar_prazo(action=acao, novo_prazo=date(2027, 1, 1), reason="", actor=engenheiro_a)


def test_repactuacao_deixa_rastro(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """Prazo empurrado sem histórico faria tudo parecer 'no prazo' no fim do ano."""
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    anterior = acao.deadline
    mudanca = repactuar_prazo(
        action=acao, novo_prazo=anterior + timedelta(days=30),
        reason="Peça importada com entrega em 45 dias.", actor=engenheiro_a,
    )
    assert mudanca.previous == anterior
    assert mudanca.dias_empurrados == 30
    assert acao.deadline_changes.count() == 1
    trilha = AuditLog.objects.filter(
        action=AuditAction.UPDATE, entity_table=acao._meta.db_table
    ).first()
    assert trilha.old_value["prazo"] == str(anterior)


# --------------------------------------------------------------------------- adequação

def test_adequacao_sobe_com_a_evidencia(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """O critério CA-08 em uma linha: a prova move o percentual."""
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    antes = adequacao(machine=maquina).percentual
    anexar_evidencia(
        action=acao, file_key="campo/1/ok.jpg", occurred_on=date(2026, 8, 1), actor=engenheiro_a
    )
    concluir_acao(action=acao, actor=engenheiro_a)
    depois = adequacao(machine=maquina).percentual
    assert antes == Decimal("0.0")
    assert depois == Decimal("100.0")


def test_curva_reconstroi_o_passado_pela_data_do_fato(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    anexar_evidencia(
        action=acao, file_key="campo/1/julho.jpg", occurred_on=date(2026, 7, 10),
        actor=engenheiro_a,
    )
    concluir_acao(action=acao, actor=engenheiro_a)
    pontos = curva_de_adequacao(client=maquina.client, meses=3, hoje=date(2026, 8, 19))
    assert pontos[-1]["percentual"] == Decimal("100.0")
    assert pontos[0]["percentual"] == Decimal("0.0")  # antes do fato


def test_geracao_nao_cria_impasse_circular(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """A ação nasce da recomendação do documento.

    Se ela bloqueasse a publicação, bloquearia o próprio documento que a recomendou — e
    o laudo nunca poderia ser emitido. Bloqueio é marca deliberada, não automática.
    """
    gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)
    assert acoes_bloqueantes_abertas(maquina) == []


def test_bloqueante_exige_motivo(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    with pytest.raises(ValueError, match="exige motivo"):
        marcar_bloqueante(action=acao, reason="", actor=engenheiro_a)


def test_bloqueante_marcada_retem_e_o_fecho_libera(
    maquina: Machine, perigo_com_medida: Hazard, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    acao = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)[0]
    marcar_bloqueante(
        action=acao, reason="Risco crítico: retém a próxima emissão até a proteção existir.",
        actor=engenheiro_a,
    )
    assert acoes_bloqueantes_abertas(maquina)
    anexar_evidencia(action=acao, file_key="campo/1/b.jpg", actor=engenheiro_a)
    concluir_acao(action=acao, actor=engenheiro_a)
    assert acoes_bloqueantes_abertas(maquina) == []


def test_vencida_aparece_nos_indicadores(
    maquina: Machine, responsavel: Person, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    plano = abrir_plano(machine=maquina, actor=engenheiro_a)
    criar_acao(
        plan=plano, text="Trocar chave geral", owner=responsavel,
        deadline=timezone.localdate() - timedelta(days=5), actor=engenheiro_a,
    )
    i = indicadores(client=maquina.client)
    assert i["vencidas"] == 1
    assert i["sem_evidencia"] == 1


def test_situacao_nao_e_coluna_do_banco() -> None:
    """Guarda-corpo: 'atrasada' derivada, nunca gravada — senão envelhece errado."""
    colunas = {f.name for f in Action._meta.get_fields() if hasattr(f, "attname")}
    assert "overdue" not in colunas
    assert "is_late" not in colunas
    assert "atrasada" not in colunas
