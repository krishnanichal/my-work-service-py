#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?The dev deployment identity must resolve to a Google Cloud project}"
: "${GITHUB_SHA:?The deployment must run with a GitHub commit SHA}"
if [[ "${ENV_NAME:-}" != dev ]]; then
  printf 'This script deploys the Work API dev service.\n' >&2
  exit 1
fi

readonly region=us-central1
readonly service=api-work-dev
readonly repository=work-api-dev
readonly registry="${region}-docker.pkg.dev"
readonly image_name="${registry}/${GCP_PROJECT_ID}/${repository}/work-api"
readonly service_url="https://run.googleapis.com/v2/projects/${GCP_PROJECT_ID}/locations/${region}/services/${service}"
readonly rollout_timeout_seconds=300
readonly poll_interval_seconds=5

cloud_run_token="$(gcloud auth print-access-token)"
readonly cloud_run_token

describe_service() {
  curl --fail --silent --show-error --max-time 15 --get "$service_url" \
    --oauth2-bearer "$cloud_run_token" --data-urlencode "fields=$1"
}

require_runtime_settings() {
  local runtime_account="cloudrun-runtime-dev@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
  if ! describe_service 'invokerIamDisabled,template(serviceAccount,containers(env(name,valueSource)))' |
    jq -e --arg runtime_account "$runtime_account" '
      .invokerIamDisabled != true and .template.serviceAccount == $runtime_account and
      (.template.containers[0].env as $env |
        any($env[]?; .name == "APP_ENV") and
        any($env[]?; .name == "APP_ALLOWED_HOSTS") and
        any($env[]?; .name == "APP_SECRETS" and
          .valueSource.secretKeyRef.secret == "app-secrets-dev" and
          .valueSource.secretKeyRef.version == "latest"))
    ' >/dev/null; then
    printf 'Could not verify the Work API dev runtime settings. Check the my-cloud-hub apply and service configuration.\n' >&2
    exit 1
  fi
}

wait_for_rollout() {
  local image="$1"
  local deadline=$((SECONDS + rollout_timeout_seconds))
  local rollout
  while (( SECONDS < deadline )); do
    rollout="$(describe_service 'reconciling,terminalCondition(state),latestCreatedRevision,latestReadyRevision,template(containers(image)),trafficStatuses(revision,percent)' |
      jq -r --arg image "$image" '
        if .template.containers[0].image != $image or .reconciling then "waiting"
        elif .terminalCondition.state == "CONDITION_FAILED" then "failed"
        elif .terminalCondition.state != "CONDITION_SUCCEEDED" or
          (.latestReadyRevision // "") == "" or
          .latestReadyRevision != .latestCreatedRevision then "waiting"
        else
          (.latestReadyRevision | split("/") | last) as $revision |
          if any(.trafficStatuses[]?;
            ((.revision // "") | split("/") | last) == $revision and .percent == 100)
          then "serving"
          else "traffic-pinned"
          end
        end
      ')"
    case "$rollout" in
      serving)
        printf 'The Work API dev revision is ready and serving all service traffic.\n'
        return 0
        ;;
      failed)
        printf 'Cloud Run rejected the Work API dev revision. Check the service revision status.\n' >&2
        return 1
        ;;
      traffic-pinned)
        printf 'The new revision is ready, but Cloud Run traffic is assigned elsewhere. Review the dev traffic settings.\n' >&2
        return 1
        ;;
    esac
    sleep "$poll_interval_seconds"
  done
  printf 'Timed out waiting for the Work API dev revision. Check the service revision status.\n' >&2
  return 1
}

require_runtime_settings

image_tag="${image_name}:${GITHUB_SHA}"
gcloud auth configure-docker "$registry" --quiet
docker tag "${repository}:${GITHUB_SHA}" "$image_tag"
docker push "$image_tag"
digest="$(docker buildx imagetools inspect "$image_tag" --format '{{.Manifest.Digest}}')"
if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  printf 'Could not resolve the published image digest.\n' >&2
  exit 1
fi
image="${image_name}@${digest}"

gcloud run services update "$service" --project="$GCP_PROJECT_ID" --region="$region" \
  --image="$image" --network=default --subnet=default --vpc-egress=private-ranges-only --async --quiet
wait_for_rollout "$image"
