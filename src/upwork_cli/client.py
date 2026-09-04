"""Upwork API client wrapper supporting both GraphQL and REST endpoints."""

from datetime import datetime
from typing import Any

import upwork
from upwork.routers import auth as upwork_auth
from upwork.routers import graphql as upwork_graphql
from upwork.routers import messages as upwork_messages
from upwork.routers.hr import engagements as hr_engagements
from upwork.routers.hr import submissions as hr_submissions
from upwork.routers.jobs import profile as job_profile
from upwork.routers.organization import companies
from upwork.routers.reports.finance import earnings as fin_earnings

from upwork_cli.config import AuthToken, Settings, load_auth, load_settings, save_auth

VENDOR_PROPOSALS_QUERY = """
query vendorProposals(
  $filter: VendorProposalFilter!,
  $sortAttribute: VendorProposalSortAttribute!,
  $pagination: Pagination!
) {
  vendorProposals(
    filter: $filter,
    sortAttribute: $sortAttribute,
    pagination: $pagination
  ) {
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      cursor
      node {
        id
        coverLetter
        proposalCoverLetter
        annotations
        status {
          status
        }
        auditDetails {
          createdDateTime
          modifiedDateTime
          statusChangedDateTime
        }
        marketplaceJobPosting {
          id
          title
          createdDateTime
        }
      }
    }
  }
}
"""

VENDOR_PROPOSAL_QUERY = """
query vendorProposal($id: ID!) {
  vendorProposal(id: $id) {
    id
    coverLetter
    proposalCoverLetter
    annotations
    status {
      status
    }
    auditDetails {
      createdDateTime
      modifiedDateTime
      statusChangedDateTime
    }
    user {
      id
      name
    }
    organization {
      id
      name
    }
    marketplaceJobPosting {
      id
      title
      description
      createdDateTime
      engagement
      durationLabel
      amount {
        amount
        currencyCode
      }
      client {
        totalHires
        totalSpent {
          amount
          currencyCode
        }
        totalFeedback
        verificationStatus
        location {
          country
        }
      }
    }
  }
}
"""

CURRENT_USER_OFFERS_QUERY = """
query currentUserOffers(
  $filter: OfferForFreelancerFilter,
  $pagination: Pagination!
) {
  user {
    offer(
      offerForFreelancerFilter: $filter,
      pagination: $pagination
    ) {
      totalCount
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        cursor
        node {
          id
          title
          state
          type
          startDateTime
          endDateTime
          lastUpdatedDateTime
          lastPublishedDateTime
          company {
            id
            name
          }
          contactPerson {
            id
            name
          }
          offer {
            id
            state
            vendorProposal {
              id
            }
          }
          contract {
            id
          }
        }
      }
    }
  }
}
"""

OFFER_QUERY = """
query offer($id: ID!) {
  offer(id: $id) {
    id
    title
    description
    type
    state
    closeJobPostingOnAccept
    messageToContractor
    client {
      id
      name
    }
    job {
      id
      title
    }
    vendorProposal {
      id
      status {
        status
      }
      marketplaceJobPosting {
        id
        title
      }
    }
    offerTerms {
      expectedStartDate
      expectedEndDate
      fixedPriceTerm {
        budget {
          amount
          currencyCode
        }
      }
      hourlyTerms {
        rate {
          amount
          currencyCode
        }
        weeklyHoursLimit
        manualTimeAllowed
      }
    }
  }
}
"""

OFFERS_BY_APPLICATION_QUERY = """
query offersByAttribute($filter: SearchOffersInput!) {
  offersByAttribute(filter: $filter) {
    offers {
      id
      title
      type
      state
      client {
        id
        name
      }
      offerTerms {
        expectedStartDate
        expectedEndDate
      }
    }
  }
}
"""

WITHDRAW_OFFER_MUTATION = """
mutation withdrawOffer($input: WithdrawOfferInput!) {
  withdrawOffer(input: $input)
}
"""


class UpworkClient:
    """Wrapper around the official Upwork SDK."""

    def __init__(
        self, settings: Settings | None = None, token: AuthToken | None = None
    ):
        self._settings = settings or load_settings()
        self._token = token or load_auth()
        self._client: upwork.Client | None = None

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

    def _graphql(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        client = self._ensure_client()
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        return upwork_graphql.Api(client).execute(payload)

    def _graphql_data(
        self, query: str, variables: dict | None = None
    ) -> dict[str, Any]:
        result = self._graphql(query, variables)
        errors = result.get("errors") or []
        if errors:
            messages = []
            for item in errors:
                if isinstance(item, dict):
                    messages.append(str(item.get("message", item)))
                else:
                    messages.append(str(item))
            raise RuntimeError("; ".join(messages))
        return result.get("data", {})

    # --- Job Search ---

    def search_jobs_graphql(
        self,
        search_term: str,
        sort_field: str = "CREATE_TIME",
        sort_order: str = "DESC",
        limit: int = 20,
    ) -> dict[str, Any]:
        # %-format on purpose: the GraphQL body is full of braces, so
        # str.format()/f-strings would need every one escaped.
        query = (
            """
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
        """  # noqa: UP031
            % limit
        )
        return self._graphql(
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

    def get_applications(
        self,
        *,
        status: str = "Accepted",
        limit: int = 20,
        sort_field: str = "ModifiedDateTime",
        sort_order: str = "DESC",
        job_posting_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search the freelancer's own submitted proposals.

        ``sort_field`` is a GraphQL enum. The default used to be spelled
        ``MODIFIEDDATETIME`` while every caller passed ``ModifiedDateTime``,
        so the two spellings of one enum sat either side of this call; the
        default now matches the value the callers actually send.
        """
        variables: dict[str, Any] = {
            "filter": {"status_eq": status},
            "sortAttribute": {
                "field": sort_field,
                "sortOrder": sort_order,
            },
            "pagination": {"first": limit},
        }
        if job_posting_ids:
            variables["filter"]["jobPostingIds_any"] = job_posting_ids
        data = self._graphql_data(VENDOR_PROPOSALS_QUERY, variables)
        return data.get("vendorProposals", {})

    def get_application(self, reference: str) -> dict[str, Any]:
        data = self._graphql_data(VENDOR_PROPOSAL_QUERY, {"id": reference})
        return data.get("vendorProposal", {})

    # --- Offers ---

    def get_offers(
        self,
        *,
        limit: int = 20,
        state: str | None = None,
        search_text: str | None = None,
    ) -> dict[str, Any]:
        filter_value: dict[str, Any] = {}
        common_filter: dict[str, Any] = {}
        if state:
            common_filter["states_any"] = [state]
        if search_text:
            common_filter["text_eq"] = search_text
        if common_filter:
            filter_value["commonFilter"] = common_filter

        variables: dict[str, Any] = {"pagination": {"first": limit}}
        if filter_value:
            variables["filter"] = filter_value

        data = self._graphql_data(CURRENT_USER_OFFERS_QUERY, variables)
        user = data.get("user", {})
        return user.get("offer", {})

    def get_offer(self, reference: str) -> dict[str, Any]:
        data = self._graphql_data(OFFER_QUERY, {"id": reference})
        return data.get("offer", {})

    def get_offers_for_application(
        self, reference: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        variables = {
            "filter": {
                "id": reference,
                "searchAttribute": "JobApplication",
                "limit": limit,
                "page": 1,
                "ascendingOrder": False,
                "includeAttachments": False,
                "includeMilestones": False,
            }
        }
        data = self._graphql_data(OFFERS_BY_APPLICATION_QUERY, variables)
        listing = data.get("offersByAttribute", {})
        return listing.get("offers", [])

    def withdraw_offer(
        self, reference: str, reason: str, message: str | None = None
    ) -> bool:
        payload: dict[str, Any] = {
            "id": reference,
            "reason": reason,
        }
        if message:
            payload["messageToClient"] = message
        data = self._graphql_data(WITHDRAW_OFFER_MUTATION, {"input": payload})
        return bool(data.get("withdrawOffer"))

    # --- Contracts / Engagements ---

    def get_engagements(self, params: dict | None = None) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_engagements.Api(client).get_list(params or {})

    def get_engagement(self, reference: str) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_engagements.Api(client).get_specific(reference)

    # --- Milestones ---

    def submit_work(self, params: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        return hr_submissions.Api(client).request_approval(params)

    # --- Messages ---

    @staticmethod
    def _paging(limit: int) -> dict[str, str]:
        """Upwork's offset;count paging string. Its spelling stays in here."""
        return {"paging": f"0;{limit}"}

    def get_rooms(self, company: str, limit: int = 20) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).get_rooms(company, self._paging(limit))

    def get_room_messages(
        self, company: str, room_id: str, limit: int = 50
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).get_room_messages(
            company, room_id, self._paging(limit)
        )

    def send_message(
        self, company: str, room_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).send_message_to_room(
            company, room_id, params
        )

    def get_room_by_contract(
        self, company: str, contract_id: str, params: dict | None = None
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return upwork_messages.Api(client).get_room_by_contract(
            company, contract_id, params or {}
        )

    # --- Earnings / Financials ---

    def get_earnings(
        self,
        freelancer_ref: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """The earnings report, optionally bounded by date.

        The report's query dialect -- a ``tq`` string of date clauses --
        is built here rather than by the caller, so nothing outside this
        class has to know it.
        """
        clauses = []
        if from_date:
            clauses.append(f"date >= '{_iso_date(from_date)}'")
        if to_date:
            clauses.append(f"date <= '{_iso_date(to_date)}'")
        params = {"tq": " AND ".join(clauses)} if clauses else {}
        client = self._ensure_client()
        return fin_earnings.Api(client).get_by_freelancer(freelancer_ref, params)

    # --- Time Reports ---

    # --- Organization ---

    def get_companies(self) -> dict[str, Any]:
        client = self._ensure_client()
        return companies.Api(client).get_list()


def _iso_date(value: str) -> str:
    """A ``YYYY-MM-DD`` date, or a refusal.

    The earnings report's ``tq`` filter is a query language, and this value
    is interpolated into it between quotes. Validating here rather than at
    the CLI means no caller -- present or future -- can put anything but a
    date into that string.
    """
    try:
        # A calendar date for a report filter, not a moment: no zone applies.
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")  # noqa: DTZ007
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Expected a date as YYYY-MM-DD, got {value!r}.") from exc


class NotAuthenticated(RuntimeError):
    """Raised when a client is requested before OAuth setup has been completed."""


def get_client() -> UpworkClient:
    """Return an authenticated client, or raise.

    The single construction site for the Upwork API. Commands call this
    rather than building a client themselves, so tests substitute one
    implementation here instead of patching the name in every module that
    imports it.
    """
    client = UpworkClient(settings=load_settings())
    if not client.is_authenticated:
        raise NotAuthenticated(
            "Not authenticated. Run 'upwork config setup' to configure your "
            "API credentials."
        )
    return client
