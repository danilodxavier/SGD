/* Aba Usuários (administradores): criar, alterar perfil, ativar/desativar, redefinir senha e desbloquear. */
"use strict";

let resetUserId = null;

function userSituation(u) {
  if (!u.active) return `<span class="badge">Desativado</span>`;
  if (u.locked_until && new Date(u.locked_until) > new Date()) return `<span class="badge err">Bloqueado</span>`;
  if (u.must_change_password) return `<span class="badge warn">Aguardando troca de senha</span>`;
  return `<span class="badge ok">Ativo</span>`;
}

async function loadUsers() {
  try {
    const { users } = await API.get("/api/users");
    const me = Auth.user ? Auth.user.id : null;
    $("#users-table tbody").innerHTML = users.map((u) => `
      <tr>
        <td><b>${esc(u.username)}</b>${u.id === me ? ` <span class="badge info">você</span>` : ""}</td>
        <td>${esc(u.name)}</td>
        <td>
          <select data-profile="${u.id}">
            <option value="consulta" ${u.profile === "consulta" ? "selected" : ""}>Consulta</option>
            <option value="admin" ${u.profile === "admin" ? "selected" : ""}>Administrador</option>
          </select>
        </td>
        <td>${userSituation(u)}</td>
        <td>${formatDate(u.last_login_at)}</td>
        <td class="actions">
          <button class="btn small" data-reset="${u.id}" data-name="${esc(u.username)}">Redefinir senha</button>
          ${u.locked_until ? `<button class="btn small" data-unlock="${u.id}">Desbloquear</button>` : ""}
          <button class="btn small" data-toggle="${u.id}" data-active="${u.active}">${u.active ? "Desativar" : "Reativar"}</button>
        </td>
      </tr>`).join("");
  } catch (e) { toast(e.message, true); }
}

$("#user-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    const u = await API.post("/api/users", {
      username: $("#new-username").value.trim(), name: $("#new-name").value.trim(),
      profile: $("#new-profile").value, password: $("#new-password").value,
    });
    ev.target.reset();
    toast(`Usuário ${u.username} criado. Informe a senha temporária pessoalmente.`);
    loadUsers();
  } catch (e) { toast(e.message, true); }
});

$("#users-table").addEventListener("change", async (ev) => {
  const id = ev.target.dataset.profile;
  if (!id) return;
  try {
    await API.put(`/api/users/${id}`, { profile: ev.target.value });
    toast("Perfil alterado.");
  } catch (e) { toast(e.message, true); }
  loadUsers();
});

$("#users-table").addEventListener("click", async (ev) => {
  const t = ev.target;
  try {
    if (t.dataset.toggle) {
      const activate = t.dataset.active !== "true";
      if (!activate && !confirm("Desativar este usuário? Ele não conseguirá mais entrar até ser reativado.")) return;
      await API.put(`/api/users/${t.dataset.toggle}`, { active: activate });
      toast(activate ? "Usuário reativado." : "Usuário desativado.");
      loadUsers();
    } else if (t.dataset.unlock) {
      await API.post(`/api/users/${t.dataset.unlock}/unlock`);
      toast("Usuário desbloqueado.");
      loadUsers();
    } else if (t.dataset.reset) {
      resetUserId = t.dataset.reset;
      $("#reset-user").textContent = t.dataset.name;
      $("#reset-password").value = "";
      $("#reset-dialog").showModal();
    }
  } catch (e) { toast(e.message, true); }
});

$("#reset-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await API.post(`/api/users/${resetUserId}/password`, { password: $("#reset-password").value });
    $("#reset-dialog").close();
    toast("Senha redefinida. O usuário deverá trocá-la no próximo acesso.");
    loadUsers();
  } catch (e) { toast(e.message, true); }
});
$("#reset-cancel").addEventListener("click", () => $("#reset-dialog").close());

views.usuarios = loadUsers;
