from rest_framework import serializers

from .models import Client, OrgUnit, Person


class ClientSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source="public_uuid", read_only=True)

    class Meta:
        model = Client
        fields = ("uuid", "legal_name", "tax_id", "cnae", "address", "contact", "status")
        read_only_fields = ("status",)


class OrgUnitSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source="public_uuid", read_only=True)
    parent = serializers.UUIDField(source="parent.public_uuid", read_only=True, allow_null=True)
    caminho = serializers.CharField(read_only=True)

    class Meta:
        model = OrgUnit
        fields = ("uuid", "kind", "name", "parent", "caminho")


class PersonSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source="public_uuid", read_only=True)
    registro = serializers.CharField(source="registro_completo", read_only=True)

    class Meta:
        model = Person
        fields = ("uuid", "name", "doc_kind", "doc_number", "roles", "registro", "email")
