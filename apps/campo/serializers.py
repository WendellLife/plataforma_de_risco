"""Contratos escritos à mão. A API expõe caso de uso, não tabela."""

from __future__ import annotations

from rest_framework import serializers


class PareamentoSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120)
    device_id = serializers.CharField(max_length=120)


class LoteSerializer(serializers.Serializer):
    client_batch_uuid = serializers.UUIDField()
    device_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    device_reported_at = serializers.DateTimeField(required=False, allow_null=True)
    records = serializers.ListField(child=serializers.DictField(), allow_empty=True, max_length=500)


class PresignSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    content_type = serializers.CharField(max_length=60)
    bytes = serializers.IntegerField(min_value=1)
