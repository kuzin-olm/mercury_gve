import asyncio
from typing import List

import aioschedule
from merc_gve.settings import logger


async def add_task_by_minutes(period_minutes: int, func: callable, params: list = None):
    params = params or []
    aioschedule.every(period_minutes).minutes.do(func, *params)


def get_user_tasks(user_id: int) -> List[aioschedule.Job]:

    jobs: List[aioschedule.Job] = aioschedule.jobs
    logger.debug(jobs)
    jobs = [
        job
        for job in jobs
        if job.job_func.args[0]["from"]["id"] == user_id or job.job_func.args[0]["chat"]["id"] == user_id
    ]
    try:
        logger.debug(jobs[0].job_func.args[0]["from"]["id"])
        logger.debug(dir(jobs[0]))
    except IndexError:
        pass
    logger.debug(len(jobs))

    return jobs


async def run_schedule_handler(*args, **kwargs):
    async def run():
        logger.debug("run schedule")
        while True:
            await aioschedule.run_pending()
            await asyncio.sleep(1)

    asyncio.create_task(run())
