import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re, platform, datetime, json

APP_TITLE = "WiFi Recovery Pro 2.0"

def netsh(args, timeout=20):
    try:
        p = subprocess.run(["netsh", "wlan"] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.stdout or p.stderr
    except Exception as exc:
        return f"Erro: {exc}"

def parse_scan():
    raw = netsh(["show", "networks", "mode=bssid"])
    items, cur = [], None
    for line in raw.splitlines():
        s = line.strip()
        m = re.match(r"SSID\s+\d+\s*:\s*(.*)", s, re.I)
        if m:
            if cur: items.append(cur)
            cur = {"SSID": m.group(1).strip() or "(sem nome)",
                   "Segurança": "Não indicada", "Encriptação": "Não indicada",
                   "Sinal": "Não indicado", "Canal": "Não indicado"}
            continue
        if cur:
            pairs = [
                (r"^(?:Authentication|Autenticação)\s*:", "Segurança"),
                (r"^(?:Encryption|Encriptação)\s*:", "Encriptação"),
                (r"^(?:Signal|Sinal)\s*:", "Sinal"),
                (r"^(?:Channel|Canal)\s*:", "Canal"),
            ]
            for pat, key in pairs:
                if re.search(pat, s, re.I):
                    cur[key] = s.split(":", 1)[1].strip()
    if cur: items.append(cur)
    return items, raw

def profiles():
    raw = netsh(["show", "profiles"])
    found = []
    patterns = [
        r"All User Profile\s*:\s*(.*)",
        r"Perfil de Todos os Utilizadores\s*:\s*(.*)",
        r"Perfil de Todos os Usuários\s*:\s*(.*)",
    ]
    for line in raw.splitlines():
        for pat in patterns:
            m = re.search(pat, line, re.I)
            if m:
                found.append(m.group(1).strip())
    return sorted(set(found), key=str.casefold)

def saved_key(profile):
    raw = netsh(["show", "profile", f"name={profile}", "key=clear"])
    for line in raw.splitlines():
        if re.search(r"(?:Key Content|Conteúdo da Chave|Conteúdo da chave)\s*:", line, re.I):
            return line.split(":", 1)[1].strip()
    return None

def adapter_info():
    raw = netsh(["show", "interfaces"])
    keep = []
    for line in raw.splitlines():
        if re.search(r"(Name|Description|GUID|Physical address|State|SSID|BSSID|Network type|Radio type|Authentication|Cipher|Channel|Receive rate|Transmit rate|Signal|Nome|Descrição|Estado|Tipo de rádio|Autenticação|Canal|Sinal)\s*:", line, re.I):
            keep.append(line.strip())
    return "\n".join(keep) if keep else raw[:3500]

def classify_security(value):
    v = value.lower()
    if "wpa3" in v: return "WPA3", "Protecção moderna; manter firmware actualizado."
    if "wpa2" in v: return "WPA2", "Em geral adequado com AES e password longa e exclusiva."
    if "wpa" in v: return "WPA (legado)", "Recomenda-se actualizar para WPA2-AES ou WPA3."
    if "wep" in v: return "WEP", "Protecção obsoleta e insegura; substituir."
    if "open" in v or "aberta" in v or "none" in v: return "Aberta", "Não protege o tráfego Wi-Fi; evitar para dados sensíveis."
    return "Não identificado", "O Windows não forneceu informação suficiente."

def make_report(networks, profs, adapter):
    lines = [
        APP_TITLE, "Relatório de diagnóstico local",
        "Data: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Sistema: " + platform.platform(), "",
        "REDES DETECTADAS"
    ]
    for n in networks:
        cls, advice = classify_security(n["Segurança"])
        lines += [
            f"- SSID: {n['SSID']}",
            f"  Segurança: {n['Segurança']} ({cls})",
            f"  Encriptação: {n['Encriptação']}",
            f"  Sinal: {n['Sinal']} | Canal: {n['Canal']}",
            f"  Nota: {advice}"
        ]
    lines += ["", "PERFIS GUARDADOS NO WINDOWS"] + [f"- {p}" for p in profs]
    lines += ["", "ADAPTADOR / LIGAÇÃO", adapter, "",
              "LIMITES: análise passiva e local. Não tenta autenticar-se em redes desconhecidas, "
              "não quebra passwords, não explora WPS nem contorna WPA/WPA2/WPA3."]
    return "\n".join(lines)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1050x720")
        self.minsize(850, 600)
        self.configure(bg="#101827")
        self.networks, self.saved_profiles = [], []
        self._style()
        self._ui()
        self.refresh_all()

    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Treeview", background="#1e293b", foreground="#f8fafc",
                     fieldbackground="#1e293b", rowheight=30, borderwidth=0)
        st.configure("Treeview.Heading", background="#334155", foreground="white",
                     font=("Segoe UI", 10, "bold"), relief="flat")
        st.map("Treeview", background=[("selected", "#047857")])
        st.configure("TButton", font=("Segoe UI", 10), padding=8)
        st.configure("TNotebook", background="#101827", borderwidth=0)
        st.configure("TNotebook.Tab", padding=(15, 9), font=("Segoe UI", 10, "bold"))

    def _ui(self):
        head = tk.Frame(self, bg="#101827")
        head.pack(fill="x", padx=22, pady=(18, 4))
        tk.Label(head, text="WiFi Recovery Pro", bg="#101827", fg="#f8fafc",
                 font=("Segoe UI", 24, "bold")).pack(side="left")
        tk.Label(head, text="2.0  •  WINDOWS", bg="#101827", fg="#34d399",
                 font=("Segoe UI", 10, "bold")).pack(side="right", pady=12)
        tk.Label(self, text="Diagnóstico automático de redes próximas e perfis guardados neste PC.",
                 bg="#101827", fg="#94a3b8", font=("Segoe UI", 10)).pack(anchor="w", padx=24, pady=(0, 12))

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=8)
        self.tab_scan = tk.Frame(self.tabs, bg="#101827")
        self.tab_saved = tk.Frame(self.tabs, bg="#101827")
        self.tab_audit = tk.Frame(self.tabs, bg="#101827")
        self.tab_adapter = tk.Frame(self.tabs, bg="#101827")
        self.tabs.add(self.tab_scan, text="Scanner Wi-Fi")
        self.tabs.add(self.tab_saved, text="Perfis guardados")
        self.tabs.add(self.tab_audit, text="Auditoria")
        self.tabs.add(self.tab_adapter, text="Adaptador")

        bar = tk.Frame(self.tab_scan, bg="#101827")
        bar.pack(fill="x", padx=12, pady=12)
        self.scan_status = tk.Label(bar, text="A preparar...", bg="#101827", fg="#e2e8f0")
        self.scan_status.pack(side="left")
        ttk.Button(bar, text="Actualizar agora", command=self.refresh_all).pack(side="right")
        cols = ("SSID", "Segurança", "Encriptação", "Sinal", "Canal")
        self.tree = ttk.Treeview(self.tab_scan, columns=cols, show="headings")
        for col, width in zip(cols, (270, 180, 160, 100, 100)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        top = tk.Frame(self.tab_saved, bg="#101827")
        top.pack(fill="x", padx=12, pady=12)
        tk.Label(top, text="Redes cujo perfil já está guardado neste computador",
                 bg="#101827", fg="#f8fafc", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Actualizar", command=self.load_profiles).pack(side="right")
        self.profile_box = tk.Listbox(self.tab_saved, bg="#1e293b", fg="#f8fafc",
                                      selectbackground="#047857", font=("Segoe UI", 11),
                                      relief="flat", height=12)
        self.profile_box.pack(fill="both", expand=True, padx=12, pady=6)
        actions = tk.Frame(self.tab_saved, bg="#101827")
        actions.pack(fill="x", padx=12, pady=10)
        ttk.Button(actions, text="Mostrar password guardada", command=self.reveal_saved).pack(side="left")
        self.key_label = tk.Label(actions, text="Apenas perfis já guardados neste PC.",
                                  bg="#101827", fg="#34d399", font=("Segoe UI", 10, "bold"))
        self.key_label.pack(side="left", padx=12)

        audit_text = (
            "RESULTADO DA AUDITORIA PASSIVA\n\n"
            "A aplicação verifica os dados que o Windows disponibiliza sem tentar entrar na rede.\n\n"
            "O que é avaliado:\n"
            "• Tipo de autenticação anunciado (WPA2/WPA3/WEP/aberta, quando disponível).\n"
            "• Tipo de encriptação anunciado.\n"
            "• Sinal e canal reportados pelo Windows.\n"
            "• Presença de um perfil local já guardado no computador.\n\n"
            "Limitações técnicas:\n"
            "• A interface padrão do Windows não disponibiliza sempre informação sobre WPS.\n"
            "• Uma análise pelo ar não revela a password de uma rede WPA2/WPA3.\n"
            "• Não são efectuadas tentativas de password, desautenticação, exploração ou bypass.\n\n"
            "Recomendações: usar WPA2-AES ou WPA3, desactivar WPS se não for necessário, "
            "actualizar o firmware e usar uma password longa e exclusiva."
        )
        tk.Label(self.tab_audit, text=audit_text, bg="#101827", fg="#dbeafe",
                 justify="left", anchor="nw", font=("Segoe UI", 10),
                 padx=18, pady=18, wraplength=900).pack(fill="both", expand=True)

        adapter_bar = tk.Frame(self.tab_adapter, bg="#101827")
        adapter_bar.pack(fill="x", padx=12, pady=12)
        ttk.Button(adapter_bar, text="Actualizar informação", command=self.load_adapter).pack(side="right")
        self.adapter_text = tk.Text(self.tab_adapter, bg="#1e293b", fg="#dbeafe",
                                    insertbackground="white", relief="flat",
                                    font=("Consolas", 10), wrap="word")
        self.adapter_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        footer = tk.Frame(self, bg="#101827")
        footer.pack(fill="x", padx=22, pady=(0, 14))
        ttk.Button(footer, text="Exportar relatório", command=self.export_report).pack(side="left")
        tk.Label(footer, text="Diagnóstico local • Sem quebra de autenticação",
                 bg="#101827", fg="#64748b", font=("Segoe UI", 9)).pack(side="right")

    def refresh_all(self):
        self.scan()
        self.load_profiles()
        self.load_adapter()

    def scan(self):
        self.networks, raw = parse_scan()
        for item in self.tree.get_children(): self.tree.delete(item)
        for n in self.networks:
            self.tree.insert("", "end", values=(n["SSID"], n["Segurança"],
                              n["Encriptação"], n["Sinal"], n["Canal"]))
        self.scan_status.config(text=f"{len(self.networks)} rede(s) detectada(s).")
        if not self.networks:
            self.scan_status.config(text="Nenhuma rede encontrada. Confirma se o Wi-Fi está ligado.")

    def load_profiles(self):
        self.saved_profiles = profiles()
        self.profile_box.delete(0, tk.END)
        for p in self.saved_profiles: self.profile_box.insert(tk.END, p)
        if not self.saved_profiles: self.profile_box.insert(tk.END, "Nenhum perfil encontrado.")

    def reveal_saved(self):
        sel = self.profile_box.curselection()
        if not sel or not self.saved_profiles:
            messagebox.showinfo(APP_TITLE, "Seleccione um perfil guardado.")
            return
        name = self.saved_profiles[sel[0]]
        key = saved_key(name)
        if key is None:
            messagebox.showwarning(APP_TITLE, "O Windows não disponibilizou uma password para este perfil.")
            return
        self.key_label.config(text=f"Password de '{name}': {key}")
        messagebox.showinfo("Credencial guardada localmente", f"Rede: {name}\nPassword: {key}")

    def load_adapter(self):
        self.adapter_text.delete("1.0", tk.END)
        self.adapter_text.insert(tk.END, adapter_info())

    def export_report(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Relatório de texto", "*.txt")],
            initialfile="Relatorio_WiFi_Recovery_Pro.txt")
        if not path: return
        report = make_report(self.networks, self.saved_profiles, adapter_info())
        with open(path, "w", encoding="utf-8") as f: f.write(report)
        messagebox.showinfo(APP_TITLE, "Relatório guardado com sucesso.")

if __name__ == "__main__":
    if platform.system() != "Windows":
        messagebox.showerror(APP_TITLE, "Esta aplicação destina-se ao Windows 10/11.")
    else:
        App().mainloop()
