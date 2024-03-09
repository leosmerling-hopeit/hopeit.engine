from hopeit.app.context import EventContext
from dataframes_example import model_storage, experiment_storage


__steps__ = [
    "init_experiment_storage",
]


async def init_experiment_storage(payload: None, context: EventContext) -> None:
    await experiment_storage.init_experiment_storage(context)
    await model_storage.init_model_storage(context)
