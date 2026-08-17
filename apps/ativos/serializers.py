from rest_framework import serializers

from .models import EnergySource, Machine


class EnergySourceSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source="public_uuid", read_only=True)
    rotulo = serializers.CharField(read_only=True)
    tem_bloqueio = serializers.SerializerMethodField()

    class Meta:
        model = EnergySource
        fields = ("uuid", "kind", "magnitude", "unit", "notes", "rotulo", "tem_bloqueio")

    def get_tem_bloqueio(self, obj: EnergySource) -> bool:
        return obj.lockout_point_id is not None


class MachineSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source="public_uuid", read_only=True)
    client = serializers.CharField(source="client.legal_name", read_only=True)
    org_unit = serializers.CharField(source="org_unit.name", read_only=True, default=None)
    energy_sources = EnergySourceSerializer(many=True, read_only=True)
    pronta_para_loto = serializers.BooleanField(read_only=True)

    class Meta:
        model = Machine
        fields = (
            "uuid", "name", "serial_number", "asset_tag", "manufacturer", "model", "year",
            "capacity", "weight_kg", "status", "client", "org_unit", "limits",
            "energy_sources", "pronta_para_loto",
        )
