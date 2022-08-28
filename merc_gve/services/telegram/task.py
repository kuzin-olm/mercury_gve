import asyncio
from typing import List

import aioschedule
from merc_gve.settings import logger


class CustomScheduler(aioschedule.Scheduler):
    async def run_pending(self, *args, **kwargs):
        jobs = [self._run_job(job) for job in self.jobs if job.should_run]
        if not jobs:
            return [], []

        return await asyncio.wait(jobs, *args, **kwargs)


async def add_task_by_minutes(period_minutes: int, func: callable, params: list = None):
    params = params or []
    aioschedule.default_scheduler.every(period_minutes).minutes.do(func, *params)


def get_user_tasks(user_id: int) -> List[aioschedule.Job]:

    jobs: List[aioschedule.Job] = aioschedule.default_scheduler.jobs
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
        aioschedule.default_scheduler = CustomScheduler()
        logger.debug("run schedule")
        while True:
            await aioschedule.run_pending()
            await asyncio.sleep(1)

    asyncio.create_task(run())
