from rest_framework import serializers


class PE10ResponseSerializer(serializers.Serializer):
    ticker = serializers.CharField()
    name = serializers.CharField()
    pe10 = serializers.FloatField(allow_null=True)
    current_price = serializers.FloatField(source="currentPrice")
    avg_adjusted_eps = serializers.FloatField(allow_null=True, source="avgAdjustedEPS")
    years_of_data = serializers.IntegerField(source="yearsOfData")
    label = serializers.CharField()
    error = serializers.CharField(allow_null=True)
