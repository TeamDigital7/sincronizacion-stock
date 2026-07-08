__all__ = ["ReconciliationResult", "StockReconciliationService"]


def __getattr__(name: str):
    if name in __all__:
        from .service import ReconciliationResult, StockReconciliationService

        return {
            "ReconciliationResult": ReconciliationResult,
            "StockReconciliationService": StockReconciliationService,
        }[name]
    raise AttributeError(name)
