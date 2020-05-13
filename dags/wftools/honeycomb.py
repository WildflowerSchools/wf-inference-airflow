import logging
import os

import boto3
import honeycomb
from gqlpycgen.utils import now


HONEYCOMB_URI = os.getenv("HONEYCOMB_URI", "https://honeycomb.api.wildflower-tech.org/graphql")
HONEYCOMB_TOKEN_URI = os.getenv("HONEYCOMB_TOKEN_URI", "https://wildflowerschools.auth0.com/oauth/token")
HONEYCOMB_AUDIENCE = os.getenv("HONEYCOMB_AUDIENCE", "https://honeycomb.api.wildflowerschools.org")
HONEYCOMB_CLIENT_ID = os.getenv("HONEYCOMB_CLIENT_ID")
HONEYCOMB_CLIENT_SECRET = os.getenv("HONEYCOMB_CLIENT_SECRET")

def get_client():
    return honeycomb.HoneycombClient(
        uri=HONEYCOMB_URI,
        client_credentials={
            'token_uri': HONEYCOMB_TOKEN_URI,
            'audience': HONEYCOMB_AUDIENCE,
            'client_id': HONEYCOMB_CLIENT_ID,
            'client_secret': HONEYCOMB_CLIENT_SECRET,
        }
    )


def get_environment_id(environment_name, honeycomb_client=None):
    if honeycomb_client is None:
        honeycomb_client = get_client()
    environments = honeycomb_client.query.findEnvironment(name=environment_name)
    return environments.data[0].get('environment_id')


def get_assignments(environment_id, honeycomb_client=None):
    if honeycomb_client is None:
        honeycomb_client = get_client()
    result = honeycomb_client.query.query(
        """
        query getEnvironment ($environment_id: ID!) {
          getEnvironment(environment_id: $environment_id) {
            environment_id
            name
            assignments(current: true) {
              assignment_id
              assigned_type
              assigned {
                ... on Device {
                    device_id
                    device_type
                }
              }
            }
          }
        }
        """,
        {"environment_id": environment_id})
    if hasattr(result, "get"):
        assignments = result.get("getEnvironment").get("assignments")
        return [(assignment["assignment_id"], assignment["assigned"]["device_id"]) for assignment in assignments if assignment["assigned_type"] == "DEVICE" and assignment["assigned"]["device_type"].find("CAMERA") > 0]
    else:
        logging.debug(result)
        return []
