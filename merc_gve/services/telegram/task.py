import asyncio
from datetime import datetime
from typing import List

import aioschedule
from merc_gve.settings import logger


class CustomJob(aioschedule.Job):
    def __init__(self, interval, scheduler=None):
        super().__init__(interval, scheduler)
        self.is_run = False

    async def run(self):
        """
        Run the job and immediately reschedule it.

        :return: The return value returned by the `job_func`
        """
        self.is_run = True
        logger.debug(f"Running task with: {self.is_run}")
        ret = await self.job_func()
        self.last_run = datetime.now()
        self.is_run = False
        self._schedule_next_run()
        return ret


class CustomScheduler(aioschedule.Scheduler):
    async def run_pending(self, *args, **kwargs):
        jobs = [self._run_job(job) for job in self.jobs if job.should_run]

        if not jobs:
            return [], []

        return await asyncio.wait(jobs, *args, **kwargs)

    def every(self, interval=1):
        job = CustomJob(interval, self)
        return job


async def add_task_by_minutes(period_minutes: int, func: callable, params: list = None):
    params = params or []
    aioschedule.default_scheduler.every(period_minutes).seconds.do(func, *params)


def get_user_tasks(user_id: int) -> List[CustomJob]:

    jobs: List[CustomJob] = aioschedule.default_scheduler.jobs
    logger.debug(jobs)
    jobs = [
        job
        for job in jobs
        if job.job_func.args[0]["from"]["id"] == user_id or job.job_func.args[0]["chat"]["id"] == user_id
    ]
    try:
        logger.debug(jobs[0].job_func.args[0]["from"]["id"])
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
