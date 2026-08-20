import { useEffect, useMemo, useState } from "react";

import CommandLayout from "../components/CommandLayout";
import { useBackendApi } from "../lib/api";
import type {
  MaintenanceEventRecord,
  OrganizationAssignment,
  OrganizationMembership,
  OrganizationWorkspace,
  OrganizationWorkspaceOperations,
  TargetProfile,
} from "../lib/types";
import { formatDate, titleCase } from "../lib/format";

const emptyWorkspace: OrganizationWorkspace = {
  organization_name: "default",
  teams: [],
  projects: [],
  memberships: [],
  removal_events: [],
  assignments: [],
  assignment_comments: [],
};

const emptyOperations: OrganizationWorkspaceOperations = {
  organization_name: "default",
  team_name: null,
  project_name: null,
  target_profiles: [],
  soak_events: [],
};

export default function AdminWorkspacePage() {
  const api = useBackendApi();
  const [configOpen, setConfigOpen] = useState(false);
  const [workspace, setWorkspace] = useState<OrganizationWorkspace>(emptyWorkspace);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("all");
  const [projectFilter, setProjectFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [assignmentStatusFilter, setAssignmentStatusFilter] = useState("all");
  const [operations, setOperations] = useState<OrganizationWorkspaceOperations>(emptyOperations);
  const [selectedMembership, setSelectedMembership] = useState<OrganizationMembership | null>(null);
  const [selectedAssignment, setSelectedAssignment] = useState<OrganizationAssignment | null>(null);
  const [selectedTargetProfile, setSelectedTargetProfile] = useState<TargetProfile | null>(null);
  const [removalReason, setRemovalReason] = useState("");
  const [assignmentComment, setAssignmentComment] = useState("");
  const [assignmentUpdate, setAssignmentUpdate] = useState({ status: "open", assigned_to: "" });
  const [teamForm, setTeamForm] = useState({ team_name: "", description: "", manager_usernames: "" });
  const [projectForm, setProjectForm] = useState({ team_name: "", project_name: "", description: "" });
  const [membershipForm, setMembershipForm] = useState({
    username: "",
    team_name: "",
    project_name: "",
    role: "operator",
    note: "",
  });
  const [assignmentForm, setAssignmentForm] = useState({
    team_name: "",
    project_name: "",
    work_type: "monitoring",
    title: "",
    subject_id: "",
    assigned_to: "",
    details: "",
  });

  const load = async (nextTeamFilter = teamFilter, nextProjectFilter = projectFilter) => {
    setLoading(true);
    const [nextWorkspace, nextOperations] = await Promise.all([
      api.getOrganizationWorkspace(),
      api.getOrganizationWorkspaceOperations({
        team_name: nextTeamFilter === "all" ? null : nextTeamFilter,
        project_name: nextProjectFilter === "all" ? null : nextProjectFilter,
      }),
    ]);
    setWorkspace(nextWorkspace);
    setOperations(nextOperations);
    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    void load(teamFilter, projectFilter);
  }, [teamFilter, projectFilter]);

  const teamOptions = useMemo(
    () => Array.from(new Set(workspace.teams.map((team) => team.team_name))).sort(),
    [workspace.teams],
  );

  const roleOptions = useMemo(
    () => Array.from(new Set(workspace.memberships.map((membership) => membership.role))).sort(),
    [workspace.memberships],
  );

  const projectOptions = useMemo(
    () => Array.from(new Set(workspace.projects.map((project) => project.project_name))).sort(),
    [workspace.projects],
  );

  const assignmentStatusOptions = useMemo(
    () => Array.from(new Set(workspace.assignments.map((assignment) => assignment.status))).sort(),
    [workspace.assignments],
  );

  const visibleMemberships = useMemo(() => {
    const query = search.trim().toLowerCase();
    return workspace.memberships.filter((membership) => {
      const haystack = [
        membership.username,
        membership.team_name,
        membership.project_name,
        membership.role,
        membership.note,
        membership.status,
      ]
        .join(" ")
        .toLowerCase();
      const matchesSearch = !query || haystack.includes(query);
      const matchesTeam = teamFilter === "all" || (membership.team_name || "unscoped") === teamFilter;
      const matchesProject = projectFilter === "all" || (membership.project_name || "shared") === projectFilter;
      const matchesRole = roleFilter === "all" || membership.role === roleFilter;
      return matchesSearch && matchesTeam && matchesProject && matchesRole;
    });
  }, [projectFilter, roleFilter, search, teamFilter, workspace.memberships]);

  const visibleAssignments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return workspace.assignments.filter((assignment) => {
      const haystack = [
        assignment.title,
        assignment.work_type,
        assignment.assigned_to,
        assignment.team_name,
        assignment.project_name,
        assignment.subject_id,
        assignment.status,
      ]
        .join(" ")
        .toLowerCase();
      const matchesSearch = !query || haystack.includes(query);
      const matchesTeam = teamFilter === "all" || (assignment.team_name || "unscoped") === teamFilter;
      const matchesProject = projectFilter === "all" || (assignment.project_name || "shared") === projectFilter;
      const matchesStatus = assignmentStatusFilter === "all" || assignment.status === assignmentStatusFilter;
      return matchesSearch && matchesTeam && matchesProject && matchesStatus;
    });
  }, [assignmentStatusFilter, projectFilter, search, teamFilter, workspace.assignments]);

  const selectedAssignmentComments = useMemo(() => {
    if (!selectedAssignment) {
      return [];
    }
    return workspace.assignment_comments.filter((comment) => comment.assignment_id === selectedAssignment.assignment_id);
  }, [selectedAssignment, workspace.assignment_comments]);

  const summary = useMemo(
    () => ({
      teams: workspace.teams.length,
      projects: workspace.projects.length,
      activeMemberships: workspace.memberships.filter((membership) => membership.status === "active").length,
      removals: workspace.removal_events.length,
      assignments: workspace.assignments.length,
      scopedTargets: operations.target_profiles.length,
      soakEvents: operations.soak_events.length,
    }),
    [operations.soak_events.length, operations.target_profiles.length, workspace],
  );

  const visibleTargetProfiles = useMemo(() => {
    const query = search.trim().toLowerCase();
    return operations.target_profiles.filter((profile) => {
      const haystack = [
        profile.name,
        profile.team_name,
        profile.project_name,
        profile.environment_name,
        profile.description,
      ]
        .join(" ")
        .toLowerCase();
      return !query || haystack.includes(query);
    });
  }, [operations.target_profiles, search]);

  const selectedTargetSoakEvents = useMemo(() => {
    if (!selectedTargetProfile) {
      return operations.soak_events.slice(0, 10);
    }
    return operations.soak_events.filter((event) => {
      const targetProfileName =
        String(event.details?.target_profile_name || event.details?.target_profile || "").trim().toLowerCase();
      return targetProfileName === selectedTargetProfile.name.trim().toLowerCase();
    });
  }, [operations.soak_events, selectedTargetProfile]);

  const handleTeamSave = async () => {
    await api.upsertOrganizationTeam({
      team_name: teamForm.team_name,
      description: teamForm.description || null,
      manager_usernames: teamForm.manager_usernames
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    });
    setMessage(`Saved team ${teamForm.team_name}`);
    setTeamForm({ team_name: "", description: "", manager_usernames: "" });
    await load();
  };

  const handleProjectSave = async () => {
    await api.upsertOrganizationProject({
      team_name: projectForm.team_name || null,
      project_name: projectForm.project_name,
      description: projectForm.description || null,
    });
    setMessage(`Saved project ${projectForm.project_name}`);
    setProjectForm({ team_name: "", project_name: "", description: "" });
    await load();
  };

  const handleMembershipSave = async () => {
    await api.upsertOrganizationMembership({
      username: membershipForm.username,
      team_name: membershipForm.team_name || null,
      project_name: membershipForm.project_name || null,
      role: membershipForm.role,
      note: membershipForm.note || null,
    });
    setMessage(`Updated membership for ${membershipForm.username}`);
    setMembershipForm({ username: "", team_name: "", project_name: "", role: "operator", note: "" });
    await load();
  };

  const handleAssignmentSave = async () => {
    await api.createOrganizationAssignment({
      team_name: assignmentForm.team_name || null,
      project_name: assignmentForm.project_name || null,
      work_type: assignmentForm.work_type,
      title: assignmentForm.title,
      subject_id: assignmentForm.subject_id || null,
      assigned_to: assignmentForm.assigned_to || null,
      details: assignmentForm.details ? { note: assignmentForm.details } : {},
    });
    setMessage(`Created assignment ${assignmentForm.title}`);
    setAssignmentForm({
      team_name: "",
      project_name: "",
      work_type: "monitoring",
      title: "",
      subject_id: "",
      assigned_to: "",
      details: "",
    });
    await load();
  };

  const handleAssignmentTransition = async () => {
    if (!selectedAssignment) {
      return;
    }
    await api.updateOrganizationAssignment(selectedAssignment.assignment_id, {
      status: assignmentUpdate.status || null,
      assigned_to: assignmentUpdate.assigned_to || null,
      comment: assignmentComment || null,
    });
    setMessage(`Updated assignment ${selectedAssignment.title}`);
    setAssignmentComment("");
    await load();
  };

  const handleAssignmentComment = async () => {
    if (!selectedAssignment || !assignmentComment.trim()) {
      return;
    }
    await api.addOrganizationAssignmentComment(selectedAssignment.assignment_id, assignmentComment.trim());
    setMessage(`Added comment to ${selectedAssignment.title}`);
    setAssignmentComment("");
    await load();
  };

  const handleRemoveMembership = async () => {
    if (!selectedMembership || !removalReason.trim()) {
      return;
    }
    await api.removeOrganizationMembership(selectedMembership.username, {
      team_name: selectedMembership.team_name || null,
      project_name: selectedMembership.project_name || null,
      reason: removalReason.trim(),
    });
    setMessage(`Removed ${selectedMembership.username} from workspace scope`);
    setRemovalReason("");
    setSelectedMembership(null);
    await load();
  };

  useEffect(() => {
    if (!selectedAssignment) {
      return;
    }
    setAssignmentUpdate({
      status: selectedAssignment.status || "open",
      assigned_to: selectedAssignment.assigned_to || "",
    });
  }, [selectedAssignment]);

  return (
    <CommandLayout
      title="Workspace governance"
      eyebrow="Org operating layer"
      description="Shape teams, projects, memberships, removals, and monitoring assignments with an explicit ledger instead of loose access sprawl."
      configOpen={configOpen}
      onOpenConfig={() => setConfigOpen(true)}
      onCloseConfig={() => setConfigOpen(false)}
      actions={
        <button className="primary-button" onClick={() => void load()} type="button">
          Refresh workspace
        </button>
      }
      meta={
        <div className="admin-access-summary">
          <article className="admin-access-stat featured">
            <span className="admin-access-stat-label">Organization</span>
            <strong>{workspace.organization_name}</strong>
            <small>One source of truth for team, project, and assignment scope.</small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Topology</span>
            <strong>{summary.teams} teams</strong>
            <small>{summary.projects} projects attached to the current workspace.</small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Active members</span>
            <strong>{summary.activeMemberships}</strong>
            <small>{summary.removals} removals captured with who + why.</small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Assigned work</span>
            <strong>{summary.assignments}</strong>
            <small>Monitor, review, soak, and incident work can be handed off cleanly.</small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Scoped targets</span>
            <strong>{summary.scopedTargets}</strong>
            <small>{summary.soakEvents} recent soak events in the current workspace slice.</small>
          </article>
        </div>
      }
    >
      <section className="glass-panel" data-reveal>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Workspace builder</span>
            <h2>Define teams, projects, memberships, and handoff lanes</h2>
          </div>
          {message ? <small>{message}</small> : null}
        </div>
        <div className="admin-workspace-grid">
          <article className="admin-workspace-card">
            <span className="eyebrow">Team</span>
            <h3>Register a team</h3>
            <label>
              <span>Name</span>
              <input
                onChange={(event) => setTeamForm((current) => ({ ...current, team_name: event.target.value }))}
                placeholder="platform"
                value={teamForm.team_name}
              />
            </label>
            <label>
              <span>Description</span>
              <input
                onChange={(event) => setTeamForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="Owns release governance and runtime safety"
                value={teamForm.description}
              />
            </label>
            <label>
              <span>Managers</span>
              <input
                onChange={(event) => setTeamForm((current) => ({ ...current, manager_usernames: event.target.value }))}
                placeholder="ganiadmin, platformlead"
                value={teamForm.manager_usernames}
              />
            </label>
            <button className="ghost-button" onClick={() => void handleTeamSave()} type="button">
              Save team
            </button>
          </article>

          <article className="admin-workspace-card">
            <span className="eyebrow">Project</span>
            <h3>Map a project lane</h3>
            <label>
              <span>Team</span>
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, team_name: event.target.value }))}
                placeholder="platform"
                value={projectForm.team_name}
              />
            </label>
            <label>
              <span>Project</span>
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, project_name: event.target.value }))}
                placeholder="lsa-core"
                value={projectForm.project_name}
              />
            </label>
            <label>
              <span>Description</span>
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="Release control plane and proof flows"
                value={projectForm.description}
              />
            </label>
            <button className="ghost-button" onClick={() => void handleProjectSave()} type="button">
              Save project
            </button>
          </article>

          <article className="admin-workspace-card">
            <span className="eyebrow">Membership</span>
            <h3>Grant workspace role</h3>
            <label>
              <span>Username</span>
              <input
                onChange={(event) => setMembershipForm((current) => ({ ...current, username: event.target.value }))}
                placeholder="operator1"
                value={membershipForm.username}
              />
            </label>
            <label>
              <span>Team</span>
              <input
                onChange={(event) => setMembershipForm((current) => ({ ...current, team_name: event.target.value }))}
                placeholder="platform"
                value={membershipForm.team_name}
              />
            </label>
            <label>
              <span>Project</span>
              <input
                onChange={(event) => setMembershipForm((current) => ({ ...current, project_name: event.target.value }))}
                placeholder="lsa-core"
                value={membershipForm.project_name}
              />
            </label>
            <label>
              <span>Role</span>
              <select
                onChange={(event) => setMembershipForm((current) => ({ ...current, role: event.target.value }))}
                value={membershipForm.role}
              >
                <option value="org_owner">Org owner</option>
                <option value="org_admin">Org admin</option>
                <option value="manager">Manager</option>
                <option value="operator">Operator</option>
                <option value="reviewer">Reviewer</option>
                <option value="viewer">Viewer</option>
              </select>
            </label>
            <label>
              <span>Note</span>
              <input
                onChange={(event) => setMembershipForm((current) => ({ ...current, note: event.target.value }))}
                placeholder="Primary owner for runtime monitoring"
                value={membershipForm.note}
              />
            </label>
            <button className="ghost-button" onClick={() => void handleMembershipSave()} type="button">
              Save membership
            </button>
          </article>

          <article className="admin-workspace-card">
            <span className="eyebrow">Assignment</span>
            <h3>Create Jira-like work handoff</h3>
            <label>
              <span>Work type</span>
              <select
                onChange={(event) => setAssignmentForm((current) => ({ ...current, work_type: event.target.value }))}
                value={assignmentForm.work_type}
              >
                <option value="monitoring">Monitoring</option>
                <option value="runtime_review">Runtime review</option>
                <option value="incident">Incident</option>
                <option value="soak_run">Soak run</option>
                <option value="target_validation">Target validation</option>
              </select>
            </label>
            <label>
              <span>Title</span>
              <input
                onChange={(event) => setAssignmentForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Own nightly soak for canary lane"
                value={assignmentForm.title}
              />
            </label>
            <label>
              <span>Assigned to</span>
              <input
                onChange={(event) => setAssignmentForm((current) => ({ ...current, assigned_to: event.target.value }))}
                placeholder="operator1"
                value={assignmentForm.assigned_to}
              />
            </label>
            <label>
              <span>Team / project</span>
              <div className="admin-workspace-inline">
                <input
                  onChange={(event) => setAssignmentForm((current) => ({ ...current, team_name: event.target.value }))}
                  placeholder="platform"
                  value={assignmentForm.team_name}
                />
                <input
                  onChange={(event) => setAssignmentForm((current) => ({ ...current, project_name: event.target.value }))}
                  placeholder="lsa-core"
                  value={assignmentForm.project_name}
                />
              </div>
            </label>
            <label>
              <span>Details</span>
              <input
                onChange={(event) => setAssignmentForm((current) => ({ ...current, details: event.target.value }))}
                placeholder="Watch drift-proof freshness after releases"
                value={assignmentForm.details}
              />
            </label>
            <button className="ghost-button" onClick={() => void handleAssignmentSave()} type="button">
              Save assignment
            </button>
          </article>
        </div>
      </section>

      <section className="glass-panel" data-reveal>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Memberships</span>
            <h2>Search active workspace membership</h2>
          </div>
        </div>
        <div className="admin-access-toolbar">
          <label className="admin-access-search">
            <span>Search</span>
            <input
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search username, team, project, role, note"
              type="search"
              value={search}
            />
          </label>
          <label className="admin-access-filter">
            <span>Team</span>
            <select onChange={(event) => setTeamFilter(event.target.value)} value={teamFilter}>
              <option value="all">All teams</option>
              {teamOptions.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-access-filter">
            <span>Role</span>
            <select onChange={(event) => setRoleFilter(event.target.value)} value={roleFilter}>
              <option value="all">All roles</option>
              {roleOptions.map((role) => (
                <option key={role} value={role}>
                  {titleCase(role)}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-access-filter">
            <span>Project</span>
            <select onChange={(event) => setProjectFilter(event.target.value)} value={projectFilter}>
              <option value="all">All projects</option>
              {projectOptions.map((project) => (
                <option key={project} value={project}>
                  {project}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-access-filter">
            <span>Assignment status</span>
            <select onChange={(event) => setAssignmentStatusFilter(event.target.value)} value={assignmentStatusFilter}>
              <option value="all">All statuses</option>
              {assignmentStatusOptions.map((status) => (
                <option key={status} value={status}>
                  {titleCase(status)}
                </option>
              ))}
            </select>
          </label>
          <div className="admin-access-filter-result">
            <span className="admin-access-stat-label">Showing</span>
            <strong>
              {visibleMemberships.length} / {workspace.memberships.length}
            </strong>
            <small>{loading ? "Refreshing workspace..." : "Click a member to prepare removal with reason."}</small>
          </div>
        </div>
        <div className="table-wrap">
          <table className="signal-table admin-access-table">
            <thead>
              <tr>
                <th className="col-summary-xxl">User</th>
                <th>Team</th>
                <th>Project</th>
                <th>Role</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleMemberships.map((membership) => (
                <tr
                  className={`interactive-row ${selectedMembership?.username === membership.username && selectedMembership?.team_name === membership.team_name && selectedMembership?.project_name === membership.project_name ? "is-selected" : ""}`}
                  key={`${membership.username}:${membership.team_name || "none"}:${membership.project_name || "none"}`}
                  onClick={() => setSelectedMembership(membership)}
                >
                  <td>
                    <div className="cell-stack">
                      <strong>{membership.username}</strong>
                      <small>{membership.note || "No membership note."}</small>
                    </div>
                  </td>
                  <td>{membership.team_name || "unscoped"}</td>
                  <td>{membership.project_name || "shared"}</td>
                  <td>
                    <span className="tone-chip neutral">{titleCase(membership.role)}</span>
                  </td>
                  <td>
                    <span className="tone-chip good">{membership.status}</span>
                  </td>
                </tr>
              ))}
              {!loading && visibleMemberships.length === 0 ? (
                <tr>
                  <td className="empty-row" colSpan={5}>
                    No memberships match the current search or filter settings.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="admin-workspace-removal">
          <div className="cell-stack">
            <strong>{selectedMembership ? `Remove ${selectedMembership.username}` : "Select a membership"}</strong>
            <small>
              {selectedMembership
                ? `${selectedMembership.team_name || "unscoped"} · ${selectedMembership.project_name || "shared"} · ${selectedMembership.role}`
                : "Click a membership row, add a reason, and the removal will be written to the ledger."}
            </small>
          </div>
          <input
            onChange={(event) => setRemovalReason(event.target.value)}
            placeholder="Reason for removal or suspension"
            value={removalReason}
          />
          <button className="ghost-button" disabled={!selectedMembership || !removalReason.trim()} onClick={() => void handleRemoveMembership()} type="button">
            Remove with reason
          </button>
        </div>
      </section>

      <section className="dashboard-grid">
        <article className="glass-panel" data-reveal>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Removal ledger</span>
              <h2>Who removed whom, and why</h2>
            </div>
          </div>
          <div className="table-wrap">
            <table className="signal-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Scope</th>
                  <th>Removed by</th>
                  <th>Reason</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {workspace.removal_events.slice(0, 12).map((event) => (
                  <tr key={event.event_id}>
                    <td>{event.username}</td>
                    <td>{event.team_name || "unscoped"} · {event.project_name || "shared"}</td>
                    <td>{event.removed_by}</td>
                    <td>{event.reason}</td>
                    <td>{formatDate(event.removed_at)}</td>
                  </tr>
                ))}
                {!workspace.removal_events.length ? (
                  <tr>
                    <td className="empty-row" colSpan={5}>
                      No removals recorded yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>

        <article className="glass-panel" data-reveal>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Assignments</span>
              <h2>Who owns monitoring, reviews, and soak work</h2>
            </div>
          </div>
          <div className="table-wrap">
            <table className="signal-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Assigned to</th>
                  <th>Scope</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {visibleAssignments.slice(0, 12).map((assignment) => (
                  <tr
                    className={`interactive-row ${selectedAssignment?.assignment_id === assignment.assignment_id ? "is-selected" : ""}`}
                    key={assignment.assignment_id}
                    onClick={() => setSelectedAssignment(assignment)}
                  >
                    <td>
                      <div className="cell-stack">
                        <strong>{assignment.title}</strong>
                        <small>{assignment.subject_id || "no subject id"}</small>
                      </div>
                    </td>
                    <td>
                      <span className="tone-chip neutral">{titleCase(assignment.work_type)}</span>
                    </td>
                    <td>{assignment.assigned_to || "unassigned"}</td>
                    <td>
                      <div className="cell-stack">
                        <strong>{assignment.team_name || "unscoped"} · {assignment.project_name || "shared"}</strong>
                        <small>{assignment.status}</small>
                      </div>
                    </td>
                    <td>{formatDate(assignment.updated_at)}</td>
                  </tr>
                ))}
                {!visibleAssignments.length ? (
                  <tr>
                    <td className="empty-row" colSpan={5}>
                      No assignments match the current filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="admin-workspace-assignment-detail">
            <div className="cell-stack">
              <strong>{selectedAssignment ? selectedAssignment.title : "Select an assignment"}</strong>
              <small>
                {selectedAssignment
                  ? `${selectedAssignment.work_type} · ${selectedAssignment.team_name || "unscoped"} · ${selectedAssignment.project_name || "shared"}`
                  : "Choose an assignment row to transition status, reassign ownership, or add notes."}
              </small>
            </div>
            <div className="admin-workspace-inline">
              <select
                disabled={!selectedAssignment}
                onChange={(event) => setAssignmentUpdate((current) => ({ ...current, status: event.target.value }))}
                value={assignmentUpdate.status}
              >
                <option value="open">Open</option>
                <option value="assigned">Assigned</option>
                <option value="in_progress">In progress</option>
                <option value="blocked">Blocked</option>
                <option value="resolved">Resolved</option>
                <option value="verified">Verified</option>
              </select>
              <input
                disabled={!selectedAssignment}
                onChange={(event) => setAssignmentUpdate((current) => ({ ...current, assigned_to: event.target.value }))}
                placeholder="reassign username"
                value={assignmentUpdate.assigned_to}
              />
            </div>
            <input
              disabled={!selectedAssignment}
              onChange={(event) => setAssignmentComment(event.target.value)}
              placeholder="Add comment or explain the transition"
              value={assignmentComment}
            />
            <div className="hero-actions">
              <button className="ghost-button" disabled={!selectedAssignment} onClick={() => void handleAssignmentTransition()} type="button">
                Save transition
              </button>
              <button className="ghost-button" disabled={!selectedAssignment || !assignmentComment.trim()} onClick={() => void handleAssignmentComment()} type="button">
                Add comment
              </button>
            </div>
            <div className="admin-workspace-comment-thread">
              {selectedAssignmentComments.slice(0, 8).map((comment) => (
                <article className="admin-workspace-comment" key={comment.comment_id}>
                  <div className="panel-heading">
                    <strong>{comment.author}</strong>
                    <small>{formatDate(comment.created_at)} · {comment.kind}</small>
                  </div>
                  <p>{comment.body}</p>
                </article>
              ))}
              {selectedAssignment && !selectedAssignmentComments.length ? (
                <div className="empty-row">No comments yet for this assignment.</div>
              ) : null}
            </div>
          </div>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="glass-panel" data-reveal>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Workspace targets</span>
              <h2>Profiles mapped into this org slice</h2>
            </div>
            <small>
              {visibleTargetProfiles.length} / {operations.target_profiles.length}
            </small>
          </div>
          <div className="table-wrap">
            <table className="signal-table">
              <thead>
                <tr>
                  <th>Profile</th>
                  <th>Team</th>
                  <th>Project</th>
                  <th>Environment</th>
                  <th>Mode</th>
                </tr>
              </thead>
              <tbody>
                {visibleTargetProfiles.slice(0, 12).map((profile) => (
                  <tr
                    className={`interactive-row ${selectedTargetProfile?.name === profile.name ? "is-selected" : ""}`}
                    key={profile.name}
                    onClick={() => setSelectedTargetProfile(profile)}
                  >
                    <td>
                      <div className="cell-stack">
                        <strong>{profile.name}</strong>
                        <small>{profile.description || "No profile description."}</small>
                      </div>
                    </td>
                    <td>{profile.team_name || "unscoped"}</td>
                    <td>{profile.project_name || "shared"}</td>
                    <td>{profile.environment_name || "default"}</td>
                    <td>
                      <span className={`tone-chip ${profile.enabled ? "good" : "warn"}`}>
                        {profile.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </td>
                  </tr>
                ))}
                {!visibleTargetProfiles.length ? (
                  <tr>
                    <td className="empty-row" colSpan={5}>
                      No target profiles match the current workspace slice.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>

        <article className="glass-panel" data-reveal>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Soak telemetry</span>
              <h2>Recent endurance history for this slice</h2>
            </div>
            <small>{selectedTargetProfile ? `Filtered by ${selectedTargetProfile.name}` : "Showing all scoped soak activity"}</small>
          </div>
          <div className="table-wrap">
            <table className="signal-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Event</th>
                  <th>Profile</th>
                  <th>Status</th>
                  <th>Actor</th>
                </tr>
              </thead>
              <tbody>
                {selectedTargetSoakEvents.slice(0, 12).map((event: MaintenanceEventRecord) => {
                  const details = event.details || {};
                  const profileName = String(details.target_profile_name || details.target_profile || "n/a");
                  const eventStatus = String(details.status || details.last_iteration_status || "unknown");
                  return (
                    <tr key={event.event_id}>
                      <td>{formatDate(event.recorded_at)}</td>
                      <td>
                        <div className="cell-stack">
                          <strong>{titleCase(event.event_type.replaceAll("_", " "))}</strong>
                          <small>{String(event.reason || "No explicit reason")}</small>
                        </div>
                      </td>
                      <td>{profileName}</td>
                      <td>
                        <span className={`tone-chip ${eventStatus === "passed" ? "good" : eventStatus === "running" ? "neutral" : "warn"}`}>
                          {eventStatus}
                        </span>
                      </td>
                      <td>{event.changed_by}</td>
                    </tr>
                  );
                })}
                {!selectedTargetSoakEvents.length ? (
                  <tr>
                    <td className="empty-row" colSpan={5}>
                      No soak telemetry recorded for the current scope yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </CommandLayout>
  );
}
