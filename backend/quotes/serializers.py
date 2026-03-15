from rest_framework import serializers


class PE10ResponseSerializer(serializers.Serializer):
    ticker = serializers.CharField()
    name = serializers.CharField()
    pe10 = serializers.FloatField(allow_null=True)
    current_price = serializers.FloatField(source="currentPrice")
    market_cap = serializers.IntegerField(allow_null=True, source="marketCap")
    avg_adjusted_net_income = serializers.FloatField(allow_null=True, source="avgAdjustedNetIncome")
    years_of_data = serializers.IntegerField(source="yearsOfData")
    label = serializers.CharField()
    error = serializers.CharField(allow_null=True)
