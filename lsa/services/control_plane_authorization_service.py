from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AuthorizedActor:
    actor_id: str
    role: str
    team: str | None
    organization: str | None = None
    auth_method: str = "unknown"


class ControlPlaneAuthorizationError(PermissionError):
    pass


@dataclass(slots=True)
class ControlPlaneAuthorizationService:
    organization_name: str
    environment_name: str
    admin_roles: tuple[str, ...] = ("admin",)
    authz_enabled: bool = False
    allowed_organizations: tuple[str, ...] = ("default",)

    def is_admin(self, actor: AuthorizedActor) -> bool:
        return actor.role in self.admin_roles

    def normalize_team(self, value: str | None) -> str | None:
        normalized = (value or "").strip().lower()
        return normalized or None

    def normalize_organization(self, value: str | None) -> str | None:
        normalized = (value or "").strip().lower()
        return normalized or None

    def require_organization_scope(self, actor: AuthorizedActor, organization_name: str | None = None) -> str:
        effective_organization = (
            self.normalize_organization(organization_name)
            or self.normalize_organization(self.organization_name)
            or "default"
        )
        if not self.authz_enabled or self.is_admin(actor):
            return effective_organization
        actor_organization = self.normalize_organization(actor.organization)
        if actor_organization is None:
            raise ControlPlaneAuthorizationError("Actor organization required for organization-scoped action.")
        allowed_organizations = {
            item for item in (self.normalize_organization(value) for value in self.allowed_organizations) if item
        }
        if allowed_organizations and actor_organization not in allowed_organizations:
            raise ControlPlaneAuthorizationError("Actor organization is not allowed by control-plane policy.")
        if actor_organization != effective_organization:
            raise ControlPlaneAuthorizationError("Actor is not authorized for this organization.")
        return effective_organization

    def require_environment_scope(self, actor: AuthorizedActor, environment_name: str | None) -> str:
        self.require_organization_scope(actor, self.organization_name)
        effective_environment = (environment_name or self.environment_name).strip().lower() or self.environment_name
        if self.authz_enabled and not self.is_admin(actor) and effective_environment != self.environment_name:
            raise ControlPlaneAuthorizationError("Actor is not authorized for this environment.")
        return effective_environment

    def require_team_scope(self, actor: AuthorizedActor, *teams: str | None) -> str | None:
        scoped_teams = {self.normalize_team(team) for team in teams if self.normalize_team(team) is not None}
        if not self.authz_enabled or self.is_admin(actor) or not scoped_teams:
            return next(iter(scoped_teams), None) if scoped_teams else self.normalize_team(actor.team)
        actor_team = self.normalize_team(actor.team)
        if actor_team is None:
            raise ControlPlaneAuthorizationError("Actor team required for team-scoped action.")
        if actor_team not in scoped_teams:
            raise ControlPlaneAuthorizationError("Actor team is not authorized for this target team.")
        return actor_team

    def scoped_owner_team(self, actor: AuthorizedActor, owner_team: str | None) -> str | None:
        if not self.authz_enabled or self.is_admin(actor):
            return self.normalize_team(owner_team)
        actor_team = self.normalize_team(actor.team)
        if actor_team is None:
            raise ControlPlaneAuthorizationError("Actor team required for owner-team scoped action.")
        if owner_team is None:
            return actor_team
        return self.require_team_scope(actor, owner_team)
