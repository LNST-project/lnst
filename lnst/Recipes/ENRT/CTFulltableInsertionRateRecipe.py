from .CTInsertionRateNftablesRecipe import CTInsertionRateNftablesRecipe
from .ConfigMixins.LongLivedConnectionsMixin import LongLivedConnectionsMixin

class CTFulltableInsertionRateRecipe(LongLivedConnectionsMixin, CTInsertionRateNftablesRecipe):
    """
    The recipe measures the insertion rate of new entries to already full conntrack table.
    Since conntrack table is implemented as hash table, "full" depends on total count of 
    available buckets. Should be more than 75%. 
    """
    pass

