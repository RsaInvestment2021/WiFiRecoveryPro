import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re, platform, datetime

APP_TITLE = "WiFi Recovery Pro 3.0"
BG = "#070B16"
PANEL = "#0D1527"
PANEL2 = "#111D33"
LINE = "#203653"
CYAN = "#29D9FF"
GREEN = "#36F5B5"
WHITE = "#EAF4FF"
MUTED = "#8BA3C2"
AMBER = "#FFC66D"


def netsh(args, timeout=25):
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
            if cur:
                items.append(cur)
            cur = {"SSID": m.group(1).strip() or "(sem nome)",
                   "Segurança": "Não indicada", "Encriptação": "Não indicada",
                   "Sinal": "Não indicado", "Canal": "Não indicado"}
            continue
        if cur:
            for pat, key in [
                (r"^(?:Authentication|Autenticação)\s*:", "Segurança"),
                (r"^(?:Encryption|Encriptação)\s*:", "Encriptação"),
                (r"^(?:Signal|Sinal)\s*:", "Sinal"),
                (r"^(?:Channel|Canal)\s*:", "Canal")]:
                if re.search(pat, s, re.I):
                    cur[key] = s.split(":", 1)[1].strip()
    if cur:
        items.append(cur)
    return items


def profiles():
    raw = netsh(["show", "profiles"])
    found = []
    pats = [r"All User Profile\s*:\s*(.*)",
            r"Perfil de Todos os Utilizadores\s*:\s*(.*)",
            r"Perfil de Todos os Usuários\s*:\s*(.*)"]
    for line in raw.splitlines():
        for pat in pats:
            m = re.search(pat, line, re.I)
            if m:
                found.append(m.group(1).strip())
    return sorted(set(found), key=str.casefold)


def saved_key(profile):
    raw = netsh(["show", "profile", f"name={profile}", "key=clear"])
    for line in raw.splitlines():
        if re.search(r"(?:Key Content|Conteúdo da Chave|Conteúdo da chave)\s*:", line, re.I):
            return line.split(":", 1)[1].strip() or None
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
    if "wpa3" in v: return "WPA3", "Protecção moderna."
    if "wpa2" in v: return "WPA2", "Adequado com AES e password exclusiva."
    if "wpa" in v: return "WPA legado", "Actualizar para WPA2-AES ou WPA3."
    if "wep" in v: return "WEP", "Protecção obsoleta."
    if "open" in v or "aberta" in v or "none" in v: return "Aberta", "Rede sem autenticação Wi-Fi."
    return "Desconhecida", "Informação limitada pelo Windows."


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x790")
        self.minsize(950, 650)
        self.configure(bg=BG)
        self.networks = []
        self.saved_profiles = []
        self.password_map = {}
        self._style()
        self._build()
        self.after(350, self.full_scan)

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview", background=PANEL2, foreground=WHITE,
                    fieldbackground=PANEL2, rowheight=38, borderwidth=0,
                    font=("Segoe UI", 10))
        s.configure("Treeview.Heading", background="#172943", foreground=CYAN,
                    font=("Segoe UI", 9, "bold"), relief="flat", padding=(9, 12))
        s.map("Treeview", background=[("selected", "#124D60")], foreground=[("selected", WHITE)])
        s.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=BG, bordercolor=BG)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                    padding=(18, 11), font=("Segoe UI", 10, "bold"))
        s.map("TNotebook.Tab", background=[("selected", "#163047")], foreground=[("selected", CYAN)])

    def panel(self, parent, **kw):
        return tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1, **kw)

    def label(self, parent, text, color=WHITE, size=10, bold=False, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", PANEL), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kw)

    def button(self, parent, text, command, primary=False, **kw):
        bg = "#073D50" if primary else "#17243A"
        fg = CYAN if primary else WHITE
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground="#14536A", activeforeground=WHITE,
                      relief="flat", bd=0, cursor="hand2",
                      font=("Segoe UI", 10, "bold"), padx=18, pady=11,
                      highlightthickness=1, highlightbackground=CYAN if primary else LINE,
                      **kw)
        b.bind("<Enter>", lambda e: b.configure(bg="#10556B" if primary else "#223653"))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 14))
        logo = tk.Frame(header, bg="#0B2637", width=48, height=48,
                        highlightbackground=CYAN, highlightthickness=1)
        logo.pack(side="left", padx=(0, 14)); logo.pack_propagate(False)
        tk.Label(logo, text="⌁", bg="#0B2637", fg=CYAN,
                 font=("Segoe UI Symbol", 30, "bold")).pack(expand=True)
        titlebox = tk.Frame(header, bg=BG); titlebox.pack(side="left")
        self.label(titlebox, "WIFI RECOVERY PRO", WHITE, 23, True, bg=BG).pack(anchor="w")
        self.label(titlebox, "LOCAL NETWORK INTELLIGENCE  /  WINDOWS", MUTED, 8, True, bg=BG).pack(anchor="w", pady=(2, 0))
        self.label(header, "V3.0  •  SYSTEM ONLINE", GREEN, 10, True, bg=BG).pack(side="right", pady=12)

        stats = tk.Frame(self, bg=BG); stats.pack(fill="x", padx=28, pady=(0, 14))
        self.stat_networks = self._stat(stats, "REDES DETECTADAS", "—", CYAN)
        self.stat_profiles = self._stat(stats, "PERFIS GUARDADOS", "—", GREEN)
        self.stat_status = self._stat(stats, "ESTADO DO SISTEMA", "READY", AMBER)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        self.tab_scan = tk.Frame(self.tabs, bg=BG)
        self.tab_audit = tk.Frame(self.tabs, bg=BG)
        self.tab_adapter = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(self.tab_scan, text="  SCANNER  ")
        self.tabs.add(self.tab_audit, text="  AUDITORIA  ")
        self.tabs.add(self.tab_adapter, text="  ADAPTADOR  ")

        intro = self.panel(self.tab_scan); intro.pack(fill="x", padx=10, pady=(12, 10))
        left = tk.Frame(intro, bg=PANEL); left.pack(side="left", padx=18, pady=15)
        self.label(left, "CENTRAL DE ANÁLISE WI-FI", WHITE, 13, True).pack(anchor="w")
        self.label(left, "Escolhe uma análise. As passwords só são apresentadas se estiverem guardadas localmente no Windows.", MUTED, 9).pack(anchor="w", pady=(5, 0))
        actions = tk.Frame(intro, bg=PANEL); actions.pack(side="right", padx=18, pady=14)
        self.button(actions, "◉  SINGLE SCAN", self.single_scan, primary=True).pack(side="left", padx=5)
        self.button(actions, "◎  FULL SCAN", self.full_scan).pack(side="left", padx=5)

        table_panel = self.panel(self.tab_scan); table_panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        top = tk.Frame(table_panel, bg=PANEL); top.pack(fill="x", padx=16, pady=(14, 8))
        self.label(top, "NETWORK DISCOVERY", CYAN, 10, True).pack(side="left")
        self.scan_status = self.label(top, "A aguardar análise...", MUTED, 9, bg=PANEL)
        self.scan_status.pack(side="right")
        cols = ("SSID", "SEGURANÇA", "SINAL", "CANAL", "PASSWORD LOCAL")
        self.tree = ttk.Treeview(table_panel, columns=cols, show="headings", selectmode="browse")
        widths = (250, 180, 110, 90, 300)
        for col, width in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, minwidth=75, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.tree.tag_configure("available", foreground=GREEN)
        self.tree.tag_configure("missing", foreground=MUTED)
        self.tree.bind("<Double-1>", lambda e: self.single_scan())

        foot = tk.Frame(self, bg=BG); foot.pack(fill="x", padx=28, pady=(0, 16))
        self.label(foot, "●  ANÁLISE LOCAL  •  SEM TENTATIVAS DE ACESSO A REDES", MUTED, 8, True, bg=BG).pack(side="left")
        self.button(foot, "EXPORTAR RELATÓRIO", self.export_report).pack(side="right")

        audit = self.panel(self.tab_audit); audit.pack(fill="both", expand=True, padx=10, pady=12)
        audit_text = ("AUDITORIA DE SEGURANÇA\n\n"
                      "A aplicação apresenta informação disponibilizada pelo Windows: autenticação, encriptação, sinal e canal.\n\n"
                      "• WPA3: padrão moderno recomendado.\n• WPA2: adequado quando configurado com AES.\n"
                      "• WEP/WPA antigo: tecnologia desactualizada.\n• Rede aberta: não oferece autenticação Wi-Fi.\n\n"
                      "As passwords apresentadas são exclusivamente as credenciais de perfis já guardados neste computador. "
                      "A aplicação não quebra passwords, não tenta autenticar-se em redes de terceiros e não contorna mecanismos de segurança.")
        self.label(audit, audit_text, WHITE, 11, bg=PANEL, justify="left", anchor="nw", padx=22, pady=22, wraplength=950).pack(fill="both", expand=True)

        adapt = self.panel(self.tab_adapter); adapt.pack(fill="both", expand=True, padx=10, pady=12)
        self.adapter_text = tk.Text(adapt, bg=PANEL2, fg=WHITE, insertbackground=CYAN,
                                    relief="flat", font=("Consolas", 10), padx=16, pady=16)
        self.adapter_text.pack(fill="both", expand=True, padx=12, pady=12)
        self.button(adapt, "ACTUALIZAR ADAPTADOR", self.load_adapter).pack(anchor="e", padx=12, pady=(0, 12))

    def _stat(self, parent, title, value, color):
        card = self.panel(parent); card.pack(side="left", fill="x", expand=True, padx=(0, 9))
        self.label(card, title, MUTED, 8, True).pack(anchor="w", padx=14, pady=(10, 2))
        v = self.label(card, value, color, 17, True); v.pack(anchor="w", padx=14, pady=(0, 10))
        return v

    def set_status(self, text, color=CYAN):
        self.stat_status.config(text=text, fg=color)
        self.scan_status.config(text=text, fg=color)
        self.update_idletasks()

    def load_data(self):
        self.set_status("SCANNING...", AMBER)
        self.networks = parse_scan()
        self.saved_profiles = profiles()
        self.password_map = {}
        for p in self.saved_profiles:
            self.password_map[p.casefold()] = saved_key(p)
        self.stat_networks.config(text=str(len(self.networks)))
        self.stat_profiles.config(text=str(len(self.saved_profiles)))
        self.tree.delete(*self.tree.get_children())
        for n in self.networks:
            key = self.password_map.get(n["SSID"].casefold())
            shown = key if key else ("Não guardada neste PC" if n["SSID"].casefold() not in self.password_map else "Password não disponível")
            tag = "available" if key else "missing"
            self.tree.insert("", "end", values=(n["SSID"], n["Segurança"], n["Sinal"], n["Canal"], shown), tags=(tag,))
        self.set_status(f"{len(self.networks)} REDES ANALISADAS", GREEN)

    def full_scan(self):
        self.load_data()
        if not self.networks:
            self.set_status("SEM REDES DETECTADAS", AMBER)

    def single_scan(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(APP_TITLE, "Selecciona primeiro uma rede na tabela.")
            return
        vals = self.tree.item(sel[0], "values")
        ssid = vals[0]
        self.set_status("A VERIFICAR PERFIL SELECCIONADO...", AMBER)
        if not self.saved_profiles:
            self.saved_profiles = profiles()
        match = next((p for p in self.saved_profiles if p.casefold() == ssid.casefold()), None)
        if not match:
            self.tree.set(sel[0], "PASSWORD LOCAL", "Não existe perfil guardado neste PC")
            self.set_status("PERFIL NÃO ENCONTRADO", AMBER)
            return
        key = saved_key(match)
        value = key if key else "Password não disponível pelo Windows"
        self.tree.set(sel[0], "PASSWORD LOCAL", value)
        self.set_status("ANÁLISE INDIVIDUAL CONCLUÍDA", GREEN if key else AMBER)

    def load_adapter(self):
        self.adapter_text.delete("1.0", tk.END)
        self.adapter_text.insert(tk.END, adapter_info())

    def export_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Relatório de texto", "*.txt")], initialfile="WiFi_Recovery_Pro_Relatorio.txt")
        if not path: return
        lines = [APP_TITLE, "Relatório de diagnóstico local", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""]
        for n in self.networks:
            pw = self.password_map.get(n["SSID"].casefold()) or "Não guardada/não disponível"
            lines.append(f"{n['SSID']} | {n['Segurança']} | {n['Sinal']} | Canal {n['Canal']} | Password local: {pw}")
        lines += ["", "As credenciais listadas são perfis guardados localmente neste computador."]
        with open(path, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        messagebox.showinfo(APP_TITLE, "Relatório exportado com sucesso.")


if __name__ == "__main__":
    if platform.system() != "Windows":
        root = tk.Tk(); root.withdraw(); messagebox.showerror(APP_TITLE, "Esta aplicação destina-se ao Windows 10/11.")
    else:
        App().mainloop()
