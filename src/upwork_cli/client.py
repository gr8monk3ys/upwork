"""Upwork API client wrapper supporting both GraphQL and REST endpoints."""

from typing import Any, Optional

import upwork
from upwork.routers import auth as upwork_auth
from upwork.routers import graphql as upwork_graphql
from upwork.routers import messages as upwork_messages
from upwork.routers.freelancers import profile as freelancer_profile
from upwork.routers.freelancers import search as freelancer_search
from upwork.routers.hr import contracts as hr_contracts
from upwork.routers.hr import engagements as hr_engagements
from upwork.routers.hr import milestones as hr_milestones
from upwork.routers.hr import submissions as hr_submissions
from upwork.routers.hr.freelancers import applications as freelancer_apps
from upwork.routers.hr.freelancers import offers as freelancer_offers
from upwork.routers.jobs import profile as job_profile
from upwork.routers.jobs import search as job_search
from upwork.routers.organization import companies, users
from upwork.routers.reports.finance import earnings as fin_earnings
from upwork.routers.reports.finance import billings as fin_billings
from upwork.routers.reports import time as time_reports

from upwork_cli.config import AuthToken, Settings, load_auth, load_settings, save_auth


class UpworkClient:
    """Wrapper around the official Upwork SDK."""

    def __init__(self, settings: Optional[Settings] = None, token: Optional[AuthToken] = None):
        self._settings = settings or load_settings()
        self._token = token or load_auth()
        self._client: Optional[upwork.Client] = None

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    def _get_config(self) -> dict[str, Any]:
        config = {
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
            "redirect_uri": self._settings.redirect_uri,
        }
        if self._token:
            config["token"] = self._token.to_dict()
        return config

    def _ensure_client(self) -> upwork.Client:
        if self._client is None:
            cfg = upwork.Config(self._get_config())
            self._client = upwork.Client(cfg)
        return self._client

    # --- Auth ---

    def get_authorization_url(self) -> str:
        client = self._ensure_client()
        url, _ = client.get_authorization_url()
        return url

    def complete_auth(self, callback_url: str) -> AuthToken:
        client = self._ensure_client()
        token_data = client.get_access_token(callback_url)
        token = AuthToken(
            access_token=token_data.get("access_token", ""),
            refresh_token=token_data.get("refresh_token", ""),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=token_data.get("expires_at", 0.0),
        )
        save_auth(token)
        self._token = token
        return token

    def get_user_info(self) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_auth.Api(client).get_user_info()

    # --- GraphQL ---

    def graphql(self, query: str, variables: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        return upwork_graphql.Api(client).execute(payload)

    # --- Job Search ---

    def search_jobs(self, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return job_search.Api(client).find(params)

    def search_jobs_graphql(
        self,
        search_term: str,
        sort_field: str = "CREATE_TIME",
        sort_order: str = "DESC",
        limit: int = 20,
    ) -> dict[str, Any]:
        query = """
        query($searchTerm: String!, $sortField: MarketplaceJobPostingSortField!, $sortOrder: SortOrder!) {
            marketplaceJobPostings(
                marketPlaceJobFilter: {
                    searchTerm_eq: { andTerms_all: $searchTerm }
                }
                sortAttributes: { field: $sortField, sortOrder: $sortOrder }
                pagination: { first: %d }
            ) {
                totalCount
                edges {
                    node {
                        id
                        ciphertext
                        title
                        createdDateTime
                        description
                        duration
                        durationLabel
                        engagement
                        amount { amount currencyCode }
                        skills { name prettyName }
                        client {
                            totalHires
                            totalSpent { amount currencyCode }
                            totalReviews
                            totalFeedback
                            verificationStatus
                            location { country }
                        }
                        occupations { category { prefLabel } subcategory { prefLabel } }
                    }
                }
            }
        }
        """ % limit
        return self.graphql(
            query,
            {
                "searchTerm": search_term,
                "sortField": sort_field,
                "sortOrder": sort_order,
            },
        )

    def get_job_detail(self, job_key: str) -> dict[str, Any]:
        client = self._ensure_client()
        return job_profile.Api(client).get_specific(job_key)

    # --- Proposals / Applications ---

    def get_applications(self, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return freelancer_apps.Api(client).get_list(params or {})

    def get_application(self, reference: str) -> dict[str, Any]:
        client = self._ensure_client()
        return freelancer_apps.Api(client).get_specific(reference)

    # --- Offers ---

    def get_offers(self, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return freelancer_offers.Api(client).get_list(params or {})

    def respond_to_offer(self, reference: str, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return freelancer_offers.Api(client).actions(reference, params)

    # --- Contracts / Engagements ---

    def get_engagements(self, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_engagements.Api(client).get_list(params or {})

    def get_engagement(self, reference: str) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_engagements.Api(client).get_specific(reference)

    def suspend_contract(self, reference: str, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_contracts.Api(client).suspend_contract(reference, params)

    def restart_contract(self, reference: str, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_contracts.Api(client).restart_contract(reference, params)

    def end_contract(self, reference: str, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_contracts.Api(client).end_contract(reference, params)

    # --- Milestones ---

    def get_active_milestone(self, contract_id: str) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_milestones.Api(client).get_active_milestone(contract_id)

    def submit_work(self, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_submissions.Api(client).request_approval(params)

    # --- Messages ---

    def get_rooms(self, company: str, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).get_rooms(company, params or {})

    def get_room_messages(self, company: str, room_id: str, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).get_room_messages(company, room_id, params or {})

    def send_message(self, company: str, room_id: str, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).send_message_to_room(company, room_id, params)

    def get_room_by_contract(self, company: str, contract_id: str, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).get_room_by_contract(company, contract_id, params or {})

    # --- Earnings / Financials ---

    def get_earnings(self, freelancer_ref: str, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return fin_earnings.Api(client).get_by_freelancer(freelancer_ref, params or {})

    def get_billings(self, freelancer_ref: str, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return fin_billings.Api(client).get_by_freelancer(freelancer_ref, params or {})

    # --- Time Reports ---

    def get_time_report(self, freelancer_id: str, params: Optional[dict] = None) -> dict[str, Any]:
        client = self._ensure_client()
        return time_reports.Api(client).get_by_freelancer_full(freelancer_id, params or {})

    # --- Organization ---

    def get_my_info(self) -> dict[str, Any]:
        client = self._ensure_client()
        return users.Api(client).get_my_info()

    def get_companies(self) -> dict[str, Any]:
        client = self._ensure_client()
        return companies.Api(client).get_list()
