"""Dados de demonstração para o primeiro deploy de teste.

Cria um tenant, dois usuários com perfis distintos, um cliente com hierarquia,
duas máquinas — uma pronta para LOTO e outra bloqueada pelo defeito D-01 —,
a biblioteca NR-12 completa e um risco com HRN inicial e residual.

    python manage.py seed_demo
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.ativos.enums import EnergyKind
from apps.ativos.models import Component, EnergySource, LockoutPoint, Machine, Project
from apps.checklists.enums import AssessmentStatus, ItemResult, Standard
from apps.checklists.models import Assessment, ItemResultRecord, LibraryItem, MachineType
from apps.clientes.enums import OrgUnitKind, PersonRole
from apps.clientes.models import Client, OrgUnit, Person
from apps.core.enums import Plan, UserRole
from apps.core.models import Tenant, User
from apps.core.tenancy import usando_tenant
from apps.documentos.models import Document
from apps.documentos.services import criar_documento, montar, sincronizar_bloqueios
from apps.risco.enums import (
    EstimateKind,
    Iso12100Step,
    Iso12100Type,
    LifecyclePhase,
    PlrValue,
    SafetyCategoryValue,
)
from apps.risco.models import Hazard, Recommendation, SafetyCategory
from apps.risco.services import registrar_estimativa


class Command(BaseCommand):
    help = "Cria dados de demonstração para o primeiro teste."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        tenant, _ = Tenant.objects.get_or_create(
            tax_id="12345678000199",
            defaults={"legal_name": "Life Laboral", "plan": Plan.PILOT, "default_locale": "pt-BR"},
        )
        self.stdout.write(f"Organização: {tenant.legal_name}")

        self._biblioteca_nr12()

        with usando_tenant(tenant.pk):
            admin = self._usuario(tenant, "admin@lifelaboral.com.br", "Ana", "Administradora", UserRole.ADMIN)
            engenheiro = self._usuario(tenant, "engenheiro@lifelaboral.com.br", "Wendell", "Engenheiro", UserRole.ENGINEER)
            analista = self._usuario(tenant, "analista@lifelaboral.com.br", "Camila", "Analista", UserRole.ANALYST)
            leitor = self._usuario(tenant, "cliente@cartonagem.com.br", "Paulo", "Cliente", UserRole.CLIENT_READER)

            tipo, _ = MachineType.objects.get_or_create(
                name="Onduladeira", defaults={"nr12_annexes": ["Anexo I", "Anexo VIII"]}
            )
            MachineType.objects.get_or_create(
                name="Injetora de plástico", defaults={"nr12_annexes": ["Anexo IX"]}
            )
            MachineType.objects.get_or_create(
                name="Prensa mecânica", defaults={"nr12_annexes": ["Anexo VIII"]}
            )

            # Marca própria no cliente: é o que faz o white-label aparecer em vez de
            # ficar só como possibilidade no modelo.
            cliente, _ = Client.objects.get_or_create(
                tenant=tenant, tax_id="98765432000155",
                defaults={
                    "brand_display_name": "Cartonagem Brasil",
                    "brand_primary": "#1B5E8C",
                    "brand_secondary": "#E8A33D",
                    "legal_name": "Papelão Industrial do Vale S.A.",
                    "cnae": "1731-1/00",
                    "address": {"municipio": "Sorocaba", "uf": "SP"},
                    "contact": {"nome": "Marcos Ribeiro", "email": "seg@papelaovale.com.br"},
                },
            )
            unidade, _ = OrgUnit.objects.get_or_create(
                tenant=tenant, client=cliente, kind=OrgUnitKind.UNIT, name="Unidade Sorocaba",
            )
            setor, _ = OrgUnit.objects.get_or_create(
                tenant=tenant, client=cliente, kind=OrgUnitKind.SECTOR,
                name="Conversão", parent=unidade,
            )

            responsavel, _ = Person.objects.get_or_create(
                tenant=tenant, doc_kind="cpf", doc_number="11122233344",
                defaults={
                    "name": "Wendell Engenheiro", "roles": [PersonRole.ENGINEER, PersonRole.RESPONSIBLE],
                    "council": "CREA", "council_state": "SP", "council_number": "5069123456",
                    "professional_title": "Engenheiro de Segurança do Trabalho",
                },
            )
            projeto, _ = Project.objects.get_or_create(
                tenant=tenant, number="CONV-1-001-001",
                defaults={"client": cliente, "name": "Adequação NR-12 — Conversão",
                          "art_number": "SP20260814-0912", "engineer": responsavel, "status": "active"},
            )

            # Máquina 1 — pronta para LOTO
            m1, criada = Machine.objects.get_or_create(
                tenant=tenant, client=cliente, name="01 - Onduladeira BHS",
                defaults={
                    "org_unit": setor, "project": projeto, "machine_type": tipo,
                    "serial_number": "BHS-2019-4471", "asset_tag": "PAT-00871",
                    "manufacturer": "BHS Corrugated", "model": "MasterLine 2.5", "year": 2019,
                    "capacity": "250 m/min", "weight_kg": Decimal("18500.00"),
                    "limits": {"velocidade": "250 m/min", "largura": "2500 mm"},
                },
            )
            if criada:
                ponto = LockoutPoint.objects.create(
                    tenant=tenant, machine=m1, identifier="QE-01",
                    location="Quadro elétrico principal, lateral esquerda",
                    device="Cadeado vermelho + garra múltipla",
                    procedure_text="Desligar o seccionador geral, aplicar garra e cadeado, "
                                   "verificar ausência de tensão com detector nas três fases.",
                )
                EnergySource.objects.create(
                    tenant=tenant, machine=m1, kind=EnergyKind.ELECTRIC,
                    magnitude=Decimal("380"), unit="V", lockout_point=ponto,
                )
                ponto2 = LockoutPoint.objects.create(
                    tenant=tenant, machine=m1, identifier="PN-01",
                    location="Unidade de tratamento de ar, entrada da linha",
                    device="Válvula de bloqueio com cadeado",
                    procedure_text="Fechar a válvula de bloqueio, cadear, acionar a purga e "
                                   "confirmar manômetro em zero.",
                )
                EnergySource.objects.create(
                    tenant=tenant, machine=m1, kind=EnergyKind.PNEUMATIC,
                    magnitude=Decimal("6.5"), unit="bar", lockout_point=ponto2,
                )
                Component.objects.create(
                    tenant=tenant, machine=m1, kind="Cortina de luz",
                    manufacturer="Sick", model="C4000", certificate_number="BR-SICK-88213",
                    certificate_valid_until="2027-03-31",
                )

            # Máquina 2 — BLOQUEADA: fonte pneumática sem ponto de bloqueio (D-01)
            m2, criada2 = Machine.objects.get_or_create(
                tenant=tenant, client=cliente, name="02 - Prensa excêntrica 60 t",
                defaults={
                    "org_unit": setor, "project": projeto,
                    "machine_type": MachineType.objects.get(name="Prensa mecânica"),
                    "serial_number": "PR-1998-0212", "manufacturer": "Nardini",
                    "model": "PE-60", "year": 1998, "capacity": "60 t",
                },
            )
            if criada2:
                ponto3 = LockoutPoint.objects.create(
                    tenant=tenant, machine=m2, identifier="QE-02",
                    location="Painel lateral direito", device="Cadeado vermelho",
                    procedure_text="Desligar o disjuntor geral e cadear.",
                )
                EnergySource.objects.create(
                    tenant=tenant, machine=m2, kind=EnergyKind.ELECTRIC,
                    magnitude=Decimal("220"), unit="V", lockout_point=ponto3,
                )
                # Sem ponto de bloqueio — é isso que o painel precisa mostrar
                EnergySource.objects.create(
                    tenant=tenant, machine=m2, kind=EnergyKind.PNEUMATIC,
                    magnitude=Decimal("0.8"), unit="bar",
                    notes="Acionamento do freio de embreagem — ponto de bloqueio não identificado em campo.",
                )

                perigo = Hazard.objects.create(
                    tenant=tenant, machine=m2, zone="Zona de prensagem",
                    title="Acesso à zona de prensagem durante o ciclo",
                    iso12100_type=Iso12100Type.MECHANICAL,
                    task="Alimentação manual de chapa",
                    existing_measures="Proteção fixa parcial na traseira.",
                )
                registrar_estimativa(
                    hazard=perigo, kind=EstimateKind.INITIAL,
                    lo=Decimal("5"), fe=Decimal("4"), dph=Decimal("8"), np=Decimal("2"),
                    actor=engenheiro,
                )
                Recommendation.objects.create(
                    tenant=tenant, hazard=perigo, iso12100_step=Iso12100Step.SAFEGUARDING,
                    text="Instalar cortina de luz categoria 4 com muting na alimentação, "
                         "integrada ao comando bimanual.",
                    device="Cortina de luz cat. 4", deadline_days=60,
                )
                registrar_estimativa(
                    hazard=perigo, kind=EstimateKind.RESIDUAL,
                    lo=Decimal("1"), fe=Decimal("2.5"), dph=Decimal("4"), np=Decimal("2"),
                    actor=engenheiro,
                )

            self._apreciacao_coerente(tenant, m1, engenheiro)
            self._checklist_encerrado(tenant, m1, engenheiro)
            self._documentos(m1, m2, engenheiro)
            self._plano_de_acao(tenant, m1, engenheiro)
            self._carteiras(cliente, admin, engenheiro, analista, leitor)

        self.stdout.write(self.style.SUCCESS(
            "Seed concluído. A máquina 01 tem uma emissão pronta para publicar e um plano de "
            "ação com os três estados que importam (concluída com evidência, vencida e a "
            "vencer); a máquina 02 está deliberadamente bloqueada pela regra D-01.\n"
            "Entre como admin@lifelaboral.com.br para ver toda a organização, ou como "
            "analista@lifelaboral.com.br para ver o escopo restrito a um cliente. "
            "Senha de todos: demo-plataforma-2026."
        ))

    def _carteiras(
        self, cliente: Client, admin: User, engenheiro: User, analista: User, leitor: User
    ) -> None:
        """Atribui carteiras para que os três escopos sejam demonstráveis no mesmo banco.

        O administrador fica SEM atribuição de propósito: perfil admin vê toda a
        organização, e dar-lhe carteira sugeriria uma restrição inexistente.
        """
        from apps.core.carteira import atribuir_cliente

        for usuario in (engenheiro, analista, leitor):
            atribuir_cliente(user=usuario, client=cliente, actor=admin)

        self.stdout.write(
            f"  acesso · {admin.email} vê toda a organização; "
            f"engenheiro, analista e cliente veem apenas {cliente.legal_name}"
        )

    def _plano_de_acao(self, tenant: Tenant, maquina: Machine, engenheiro: User) -> None:
        """Plano com os três estados que a tela precisa provar.

        Uma ação encerrada com evidência DATADA NO PASSADO — é o que faz a curva de
        adequação mostrar movimento em vez de um degrau em "hoje". Uma vencida e uma a
        vencer, para o painel nascer com os alertas reais em vez de tudo verde.
        """
        from datetime import timedelta

        from apps.planos.models import Action
        from apps.planos.services import (
            abrir_plano,
            anexar_evidencia,
            concluir_acao,
            gerar_acoes_de_nao_conformidade,
        )

        # Quem executa a adequação é a manutenção, não o engenheiro que apreciou o risco.
        # Separar os dois é o que faz a tela "carga por responsável" dizer algo.
        executor, _ = Person.objects.get_or_create(
            tenant=tenant, doc_kind="cpf", doc_number="99988877766",
            defaults={"name": "Jonas Ribeiro", "roles": [PersonRole.RESPONSIBLE]},
        )
        plano = abrir_plano(machine=maquina, actor=engenheiro)
        criadas = gerar_acoes_de_nao_conformidade(
            machine=maquina, owner=executor, actor=engenheiro
        )
        if not criadas:
            criadas = list(Action.objects.filter(plan=plano))
        if not criadas:
            self.stdout.write("  plano de ação: nenhum achado a converter")
            return

        hoje = timezone.localdate()

        # 1ª ação: executada de fato há 40 dias, com nota fiscal. Move a curva no passado.
        concluida = criadas[0]
        if concluida.status != "done":
            anexar_evidencia(
                action=concluida, file_key=f"planos/{tenant.pk}/nf-protecao-fixa.pdf",
                kind="invoice", caption="Nota fiscal da proteção fixa com interbloqueio",
                occurred_on=hoje - timedelta(days=40), actor=engenheiro,
            )
            concluir_acao(action=concluida, actor=engenheiro)

        # 2ª ação: vencida há 12 dias e sem evidência — o alerta que o gestor precisa ver.
        if len(criadas) > 1:
            vencida = criadas[1]
            vencida.deadline = hoje - timedelta(days=12)
            vencida.save(update_fields=["deadline"])

        # 3ª ação: vence em 6 dias, dentro da janela de alerta de 15.
        if len(criadas) > 2:
            a_vencer = criadas[2]
            a_vencer.deadline = hoje + timedelta(days=6)
            a_vencer.status = "in_progress"
            a_vencer.save(update_fields=["deadline", "status"])

        self.stdout.write(
            f"  plano {plano.number} · {len(criadas)} ação(ões) "
            "(1 concluída com evidência de 40 dias atrás, 1 vencida, 1 a vencer)"
        )

    def _apreciacao_coerente(self, tenant: Tenant, maquina: Machine, engenheiro: User) -> None:
        """Máquina 01: apreciação completa e coerente — o caminho que PUBLICA."""
        if maquina.hazards.exists():
            return
        perigo = Hazard.objects.create(
            tenant=tenant, machine=maquina, zone="Zona de entrada de papel",
            title="Arrastamento entre cilindros de tração",
            iso12100_type=Iso12100Type.MECHANICAL, lifecycle_phase=LifecyclePhase.OPERATION,
            task="Emenda de bobina em movimento",
            existing_measures="Proteção fixa lateral e parada de emergência ao alcance.",
        )
        registrar_estimativa(
            hazard=perigo, kind=EstimateKind.INITIAL,
            lo=Decimal("5"), fe=Decimal("4"), dph=Decimal("8"), np=Decimal("2"), actor=engenheiro,
        )
        Recommendation.objects.create(
            tenant=tenant, hazard=perigo, iso12100_step=Iso12100Step.SAFEGUARDING,
            text="Instalar proteção móvel com interbloqueio e bloqueio de guarda na entrada, "
                 "integrada ao circuito de parada categoria 3.",
            device="Chave de segurança com bloqueio", deadline_days=45,
        )
        registrar_estimativa(
            hazard=perigo, kind=EstimateKind.RESIDUAL,
            lo=Decimal("1"), fe=Decimal("2.5"), dph=Decimal("2"), np=Decimal("2"), actor=engenheiro,
        )
        SafetyCategory.objects.create(
            tenant=tenant, hazard=perigo, s=2, f=2, p=1,
            category=SafetyCategoryValue.C3, plr=PlrValue.D,
            rationale="Gravidade alta com exposição frequente e possibilidade de evitar reduzida.",
        )

    def _checklist_encerrado(self, tenant: Tenant, maquina: Machine, coletor: User) -> None:
        """Checklist NR-12 encerrado — dá conteúdo ao relatório de conformidade."""
        if Assessment.objects.filter(machine=maquina, standard=Standard.NR12).exists():
            return
        base = LibraryItem.objects.filter(standard=Standard.NR12, retired_at__isnull=True)
        avaliacao = Assessment.objects.create(
            tenant=tenant, machine=maquina, standard=Standard.NR12,
            library_base_count=base.count(), status=AssessmentStatus.CLOSED,
            collected_by=coletor, closed_at=timezone.now(),
        )
        itens = list(base.order_by("display_order")[:18])
        for indice, item in enumerate(itens):
            if indice % 6 == 5:
                resultado, justificativa = ItemResult.NOT_APPLICABLE, (
                    "Requisito de anexo não aplicável ao tipo desta máquina; "
                    "exclusão registrada em campo com foto da configuração."
                )
            elif indice % 5 == 3:
                resultado, justificativa = ItemResult.NON_COMPLIANT, ""
            elif indice % 7 == 4:
                resultado, justificativa = ItemResult.PARTIAL, ""
            else:
                resultado, justificativa = ItemResult.COMPLIANT, ""
            ItemResultRecord.objects.create(
                tenant=tenant, assessment=avaliacao, library_item=item,
                result=resultado, justification=justificativa,
                note="Verificado em vistoria presencial." if resultado == ItemResult.NON_COMPLIANT else "",
            )
        self.stdout.write(
            f"  checklist NR-12 encerrado com {len(itens)} respostas sobre base de {base.count()}"
        )

    def _documentos(self, maquina_ok: Machine, maquina_travada: Machine, engenheiro: User) -> None:
        """Uma emissão pronta para publicar e uma emissão travada pelo verificador."""
        planos = (
            (maquina_ok, ("DOC01", "DOC02", "DOC03")),
            (maquina_travada, ("DOC01",)),
        )
        for maquina, codigos in planos:
            for codigo in codigos:
                if Document.objects.filter(machine=maquina, template_code=codigo).exists():
                    continue
                documento = criar_documento(
                    machine=maquina, template_code=codigo, actor=engenheiro
                )
                contexto = montar(documento=documento)
                bloqueios = sincronizar_bloqueios(documento=documento, contexto=contexto)
                situacao = f"{bloqueios} bloqueio(s)" if bloqueios else "pronto para publicar"
                self.stdout.write(f"  {codigo} · {maquina.name} · {situacao}")

    def _usuario(self, tenant: Tenant, email: str, nome: str, sobrenome: str, role: str) -> User:
        user, criado = User.objects.get_or_create(
            username=email,
            defaults={"tenant": tenant, "email": email, "first_name": nome,
                      "last_name": sobrenome, "role": role},
        )
        if criado:
            user.mfa_enabled = user.exige_mfa
            user.set_password("demo-plataforma-2026")
            user.save()
            self.stdout.write(f"  usuário {email} · senha demo-plataforma-2026")
        return user

    def _biblioteca_nr12(self) -> None:
        caminho = Path(settings.BASE_DIR) / "apps" / "checklists" / "fixtures" / "nr12.json"
        itens = json.loads(caminho.read_text(encoding="utf-8"))
        criados = 0
        for item in itens:
            _, criado = LibraryItem.objects.get_or_create(
                standard=Standard.NR12, library_key=item["library_key"], version=1,
                defaults={
                    "group_name": item["group_name"],
                    "statement": item["statement"],
                    "display_order": item["display_order"],
                },
            )
            criados += int(criado)
        self.stdout.write(f"Biblioteca NR-12: {len(itens)} itens ({criados} novos)")
