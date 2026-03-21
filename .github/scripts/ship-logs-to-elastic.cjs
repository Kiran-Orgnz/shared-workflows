// .github/scripts/ship-job-results.cjs
module.exports = async ({ github, context, core }) => {
    const runId = context.runId;
  
    const { data } = await github.rest.actions.listJobsForWorkflowRun({
      owner: context.repo.owner,
      repo: context.repo.repo,
      run_id: runId,
    });
  
    const jobs = data.jobs.filter(
      (job) =>
        (!!job.conclusion && job.conclusion !== "skipped") &&
        !job.name?.toLowerCase().includes("notify")
    );
  
    const elasticHost = process.env.ELASTIC_HOST;
    const elasticIndex = process.env.ELASTIC_INDEX;
    const elasticKey = process.env.ELASTIC_KEY;
  
    if (!elasticHost || !elasticIndex || !elasticKey) {
      core.setFailed("Missing ELASTIC_HOST / ELASTIC_INDEX / ELASTIC_KEY");
      return;
    }
  
    const elasticUrl = `${elasticHost}/${elasticIndex}/_doc`;
    core.info(`Posting to URL = ${elasticUrl}`);
  
    for (const job of jobs) {
      const body = {
        "@timestamp": job.completed_at,
        job_name: job.name,
        status: job.status,
        conclusion: job.conclusion,
        started_at: job.started_at,
        completed_at: job.completed_at,
        owner: context.repo.owner,
        repo: context.repo.repo,
        run_id: context.runId,
        release_id: process.env.RELEASE_TAG,
        env: process.env.HELM_ENV,
        actor: process.env.ACTOR,
        origin: "github",
      };
  
      const response = await fetch(elasticUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `ApiKey ${elasticKey}`,
        },
        body: JSON.stringify(body),
      });
  
      
      if (!response.ok) {
        const txt = await response.text().catch(() => "");
        core.warning(`Elastic error: ${response.status} ${response.statusText} ${txt}`);
      } else {
        core.info(`Indexed job ${job.name}`);
      }
    }
  };