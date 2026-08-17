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

from apps.ativos.enums import EnergyKind
from apps.ativos.models import Component, EnergySource, LockoutPoint, Machine, Project
from apps.checklists.enums import Standard
from apps.checklists.models import LibraryItem, MachineType
from apps.clientes.enums import OrgUnitKind, PersonRole
from apps.clientes.models import Client, OrgUnit, Person
from apps.core.enums import Plan, UserRole
from apps.core.models import Tenant, User
from apps.core.tenancy import usando_tenant
from apps.risco.enums import EstimateKind, Iso12100Step, Iso12100Type
from apps.risco.models import Hazard, Recommendation
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
            engenheiro = self._usuario(tenant, "engenheiro@lifelaboral.com.br", "Wendell", "Engenheiro", UserRole.ENGINEER)
            self._usuario(tenant, "analista@lifelaboral.com.br", "Camila", "Analista", UserRole.ANALYST)

            tipo, _ = MachineType.objects.get_or_create(
                name="Onduladeira", defaults={"nr12_annexes": ["Anexo I", "Anexo VIII"]}
            )
            MachineType.objects.get_or_create(
                name="Injetora de plástico", defaults={"nr12_annexes": ["Anexo IX"]}
            )
            MachineType.objects.get_or_create(
                name="Prensa mecânica", defaults={"nr12_annexes": ["Anexo VIII"]}
            )

            cliente, _ = Client.objects.get_or_create(
                tenant=tenant, tax_id="98765432000155",
                defaults={
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
                    lo=Decimal("1.5"), fe=Decimal("2.5"), dph=Decimal("4"), np=Decimal("2"),
                    actor=engenheiro,
                )

        self.stdout.write(self.style.SUCCESS(
            "Seed concluído. Máquina 02 está deliberadamente bloqueada pela regra D-01 — "
            "é o que o painel deve mostrar."
        ))

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
