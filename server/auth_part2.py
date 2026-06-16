from server.auth_shared import *

class AuthMixinPart2(BaseHandler):
    def _user_create(self, d):
        u = self._get_current_user()
        if not u or u["role"] not in ("admin", "manager"): return self._redirect("/?flash=无权限访问")
        username = qs(d, "username", "").strip()
        password = qs(d, "password", "")
        if not username or not password: return self._redirect("/users/create?flash=用户名和密码不能为空")
        role = qs(d, "role", "finance")
        if role in ("admin", "system_admin"):
            return self._redirect("/users?flash=超级管理员账号不可新增")
        if u["role"] == "manager" and role in ("admin", "system_admin", "manager"):
            return self._redirect("/users?flash=业务管理员只能创建财务、收费员、客服或管理层只读账号")
        pw_hash = hash_password(password)
        db = get_db()
        try:
            db.execute("INSERT INTO users(username,password_hash,display_name,role) VALUES(?,?,?,?)",
                       (username, pw_hash, qs(d,"display_name"), role))
            db.commit()
        except:
            db.close(); return self._redirect("/users/create?flash=用户名已存在")
        db.close()
        self._redirect("/users?flash=添加成功")

    def _user_edit(self, uid, d):
        u = self._get_current_user()
        if not u or u["role"] not in ("admin", "manager"): return self._redirect("/?flash=无权限访问")
        username = qs(d, "username", "").strip()
        password = qs(d, "password", "")
        if not username: return self._redirect(f"/users/{uid}/edit?flash=用户名不能为空")
        db = get_db()
        target = db.execute("SELECT username,role FROM users WHERE id=?", (uid,)).fetchone()
        if not target:
            db.close(); return self._redirect("/users?flash=操作员不存在或已删除")
        new_role = qs(d, "role", "finance")
        if target["role"] not in ("admin", "system_admin") and new_role in ("admin", "system_admin"):
            db.close(); return self._redirect("/users?flash=超级管理员账号不可新增或升级")
        if target["username"] == "admin" and new_role not in ("admin", "system_admin"):
            db.close(); return self._redirect("/users?flash=超级管理员不可降级")
        if u["role"] == "manager" and (target["role"] in ("admin", "system_admin") or new_role in ("admin", "system_admin", "manager")):
            db.close(); return self._redirect("/users?flash=业务管理员不能管理超级管理员或业务管理员")
        if password:
            pw_hash = hash_password(password)
            db.execute("UPDATE users SET username=?,password_hash=?,display_name=?,role=?,is_active=? WHERE id=?",
                       (username, pw_hash, qs(d,"display_name"), new_role, 1 if qs(d,"is_active") else 0, uid))
        else:
            db.execute("UPDATE users SET username=?,display_name=?,role=?,is_active=? WHERE id=?",
                       (username, qs(d,"display_name"), new_role, 1 if qs(d,"is_active") else 0, uid))
        db.commit(); db.close()
        self._redirect("/users?flash=更新成功")

    def _user_delete(self, uid):
        u = self._get_current_user()
        if not u or u["role"] not in ("admin", "manager"): return self._redirect("/?flash=无权限访问")
        db = get_db()
        target = db.execute("SELECT username,role FROM users WHERE id=?", (uid,)).fetchone()
        if target and target["username"] == "admin":
            db.close()
            return self._redirect("/users?flash=超级管理员不可删除")
        if target and u["role"] == "manager" and target["role"] in ("admin", "manager"):
            db.close()
            return self._redirect("/users?flash=业务管理员不能删除超级管理员或业务管理员")
        db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        db.execute("DELETE FROM users WHERE id=?", (uid,))
        db.commit(); db.close()
        self._redirect("/users?flash=已删除")
