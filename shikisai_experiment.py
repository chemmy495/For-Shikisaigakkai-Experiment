"""
shikisai_experiment.py
WS2812B LED 色識別実験 (Python / tkinter GUI)

依存: pyserial
    pip install pyserial

使い方:
  1. Arduinoに shikisai_led.ino を書き込む
  2. COM9 に接続されていることを確認
  3. このスクリプトを実行
  4. 「実験開始」ボタンを押して試行を繰り返す
  5. 「実験終了・保存」で CSV を任意の場所に保存

回答キー:
  F キー → 同じ色
  J キー → 違う色
"""

import csv
import random
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import serial
import serial.tools.list_ports

# ============================================================
# 実験パラメータ (必要に応じて変更)
# ============================================================

# 4色の定義: {"変数名": (R, G, B)}
COLORS = {
    "Color_A": (255,   0,   0),   # 赤
    "Color_B": (  0, 255,   0),   # 緑
    "Color_C": (  0,   0, 255),   # 青
    "Color_D": (255, 255,   0),   # 黄
}

COM_PORT      = "COM9"
BAUD_RATE     = 9600
DISPLAY_TIME  = 2.0          # 各色の表示時間 [秒]
BLANK_MIN     = 2.0          # 空白期間の最短 [秒]
BLANK_MAX     = 5.0          # 空白期間の最長 [秒]

# ============================================================


class ExperimentApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("色識別実験")
        self.resizable(False, False)

        self._serial: serial.Serial | None = None
        self._trial_data: list[dict] = []
        self._trial_num = 0
        self._response_start: float | None = None
        self._color1: str | None = None
        self._color2: str | None = None
        self._waiting_response = False
        self._running = False           # 試行中フラグ (UI 操作ロック用)
        self._brightness = 80           # 現在の輝度 (0-255)

        self._build_ui()
        self._connect_arduino()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------

    def _build_ui(self):
        pad = dict(padx=12, pady=6)

        # --- 上部: ステータスと試行番号 ---
        top = tk.Frame(self, bg="#1e1e2e", pady=10)
        top.pack(fill=tk.X)

        self._lbl_status = tk.Label(
            top, text="接続中...", font=("Meiryo UI", 12),
            bg="#1e1e2e", fg="#cdd6f4"
        )
        self._lbl_status.pack()

        self._lbl_trial = tk.Label(
            top, text="試行 0 回目", font=("Meiryo UI", 10),
            bg="#1e1e2e", fg="#a6adc8"
        )
        self._lbl_trial.pack()

        # --- 輝度設定 ---
        bright_frame = tk.Frame(self, bg="#1e1e2e", pady=6)
        bright_frame.pack(fill=tk.X)

        tk.Label(
            bright_frame, text="輝度 (0–255):",
            font=("Meiryo UI", 10), bg="#1e1e2e", fg="#cdd6f4"
        ).pack(side=tk.LEFT, padx=(12, 4))

        self._brightness_var = tk.IntVar(value=80)

        self._scale_bright = tk.Scale(
            bright_frame, from_=0, to=255, orient=tk.HORIZONTAL,
            variable=self._brightness_var, length=200,
            bg="#1e1e2e", fg="#cdd6f4", troughcolor="#313244",
            activebackground="#89b4fa", highlightthickness=0,
            showvalue=False, command=self._on_brightness_scale
        )
        self._scale_bright.pack(side=tk.LEFT, padx=(0, 4))

        vcmd = self.register(self._validate_brightness)
        self._entry_bright = tk.Entry(
            bright_frame, textvariable=self._brightness_var, width=5,
            font=("Meiryo UI", 10), bg="#313244", fg="#cdd6f4",
            insertbackground="#cdd6f4", relief=tk.FLAT,
            validate="key", validatecommand=(vcmd, "%P")
        )
        self._entry_bright.pack(side=tk.LEFT, padx=(0, 4))
        self._entry_bright.bind("<Return>",   self._on_brightness_entry)
        self._entry_bright.bind("<FocusOut>", self._on_brightness_entry)

        # --- 中央: 状態・操作案内 ---
        mid = tk.Frame(self, bg="#181825", pady=24)
        mid.pack(fill=tk.X)

        self._lbl_phase = tk.Label(
            mid, text="実験開始を押してください",
            font=("Meiryo UI", 13), bg="#181825", fg="#89b4fa"
        )
        self._lbl_phase.pack(pady=(0, 4))

        self._lbl_key_hint = tk.Label(
            mid, text="同じ色: [F]キー  |  違う色: [J]キー",
            font=("Meiryo UI", 11), bg="#181825", fg="#a6adc8"
        )
        self._lbl_key_hint.pack()

        # --- キーボードバインド ---
        self.bind("<f>", lambda e: self._record_response(True))   # F = 同じ
        self.bind("<j>", lambda e: self._record_response(False))  # J = 違う

        # --- 下部: 制御ボタン ---
        bot = tk.Frame(self, bg="#1e1e2e", pady=10)
        bot.pack(fill=tk.X)

        self._btn_start = tk.Button(
            bot, text="実験開始",
            font=("Meiryo UI", 12), width=14,
            bg="#89b4fa", fg="#1e1e2e", relief=tk.FLAT,
            command=self._start_trial,
            state=tk.DISABLED
        )
        self._btn_start.pack(side=tk.LEFT, **pad)

        self._btn_save = tk.Button(
            bot, text="実験終了・保存",
            font=("Meiryo UI", 12), width=14,
            bg="#fab387", fg="#1e1e2e", relief=tk.FLAT,
            command=self._save_csv,
            state=tk.DISABLED
        )
        self._btn_save.pack(side=tk.RIGHT, **pad)

        self.configure(bg="#181825")

    # ----------------------------------------------------------
    # 輝度コントロール
    # ----------------------------------------------------------

    def _validate_brightness(self, val: str) -> bool:
        """Entry の入力バリデーション: 空欄 or 0–255 の整数のみ許可"""
        if val == "":
            return True
        try:
            return 0 <= int(val) <= 255
        except ValueError:
            return False

    def _on_brightness_scale(self, val: str):
        """Scale を動かしたとき: Entry と同期して Arduino に送信"""
        v = int(float(val))
        self._brightness_var.set(v)
        self._apply_brightness(v)

    def _on_brightness_entry(self, _event=None):
        """Entry で Enter / フォーカスアウト時: 値を整形して Arduino に送信"""
        try:
            v = max(0, min(255, int(self._brightness_var.get())))
        except (ValueError, tk.TclError):
            v = self._brightness          # 無効値なら元の値に戻す
        self._brightness_var.set(v)
        self._scale_bright.set(v)
        self._apply_brightness(v)

    def _apply_brightness(self, value: int):
        """輝度値を保存し、Arduino に非同期送信"""
        self._brightness = value
        if self._serial and self._serial.is_open:
            threading.Thread(
                target=lambda: self._send_command(f"BRIGHTNESS {value}"),
                daemon=True
            ).start()

    # ----------------------------------------------------------
    # Arduino 接続
    # ----------------------------------------------------------

    def _connect_arduino(self):
        def _try_connect():
            try:
                ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=3)
                time.sleep(2)  # Arduino リセット待ち
                # READY 受信まで待機
                deadline = time.time() + 5
                while time.time() < deadline:
                    if ser.in_waiting:
                        line = ser.readline().decode(errors="ignore").strip()
                        if line == "READY":
                            break
                self._serial = ser
                self.after(0, self._on_connected)
            except serial.SerialException as e:
                self.after(0, lambda: self._on_connect_failed(str(e)))

        threading.Thread(target=_try_connect, daemon=True).start()

    def _on_connected(self):
        self._lbl_status.config(text=f"Arduino 接続済み ({COM_PORT})", fg="#a6e3a1")
        self._btn_start.config(state=tk.NORMAL)

    def _on_connect_failed(self, err: str):
        self._lbl_status.config(
            text=f"接続失敗: {err}", fg="#f38ba8"
        )
        messagebox.showerror(
            "接続エラー",
            f"Arduino に接続できませんでした。\n\n"
            f"ポート: {COM_PORT}\nエラー: {err}\n\n"
            f"接続を確認して再起動してください。"
        )

    def _send_command(self, cmd: str):
        """シリアルコマンド送信 → "OK" 応答を待つ"""
        if self._serial and self._serial.is_open:
            self._serial.write((cmd + "\n").encode())
            deadline = time.time() + 3
            while time.time() < deadline:
                if self._serial.in_waiting:
                    resp = self._serial.readline().decode(errors="ignore").strip()
                    if resp == "OK":
                        return
            # タイムアウトしても続行 (LED 動作は維持される)

    # ----------------------------------------------------------
    # 試行制御
    # ----------------------------------------------------------

    def _start_trial(self):
        if self._running:
            return
        self._running = True
        self._btn_start.config(state=tk.DISABLED)
        self._lbl_phase.config(text="準備中…")

        threading.Thread(target=self._trial_thread, daemon=True).start()

    def _trial_thread(self):
        color_names = list(COLORS.keys())

        # ランダムに2色選択 (同色も有り得る)
        c1_name = random.choice(color_names)
        c2_name = random.choice(color_names)
        self._color1 = c1_name
        self._color2 = c2_name

        r1, g1, b1 = COLORS[c1_name]
        r2, g2, b2 = COLORS[c2_name]

        # --- 1色目表示 ---
        self._send_command(f"SHOW {r1} {g1} {b1}")
        time.sleep(DISPLAY_TIME)

        # --- 消灯 ---
        self._send_command("OFF")

        # --- ランダム空白 ---
        blank = random.uniform(BLANK_MIN, BLANK_MAX)
        time.sleep(blank)

        # --- 2色目表示 → 同時に回答受付開始・タイマー計測開始 ---
        self._send_command(f"SHOW {r2} {g2} {b2}")
        self._response_start = time.perf_counter()
        self.after(0, self._enable_response)
        time.sleep(DISPLAY_TIME)

        # --- 消灯 (回答受付は継続中) ---
        self._send_command("OFF")
        self.after(0, lambda: self._lbl_phase.config(
            text="1色目と2色目は同じでしたか？"
        ))

    def _enable_response(self):
        self._trial_num += 1
        self._lbl_trial.config(text=f"試行 {self._trial_num} 回目")
        self._lbl_phase.config(text="回答してください")
        self._lbl_key_hint.config(text="同じ色: [F]キー  |  違う色: [J]キー")
        self._waiting_response = True

    def _record_response(self, user_says_same: bool):
        if not self._waiting_response:
            return
        self._waiting_response = False

        rt_ms = round((time.perf_counter() - self._response_start) * 1000)

        correct_same = (self._color1 == self._color2)
        is_correct = (user_says_same == correct_same)
        correct_ans = "同じ" if correct_same else "違う"
        user_ans    = "同じ" if user_says_same  else "違う"

        row = {
            "trial":       self._trial_num,
            "color1":      self._color1,
            "color2":      self._color2,
            "correct_ans": correct_ans,
            "user_ans":    user_ans,
            "is_correct":  "○" if is_correct else "×",
            "rt_ms":       rt_ms,
            "brightness":  self._brightness,
        }
        self._trial_data.append(row)

        self._lbl_phase.config(text="実験開始を押してください")
        self._running = False
        self._btn_start.config(state=tk.NORMAL, text="次の試行")
        self._btn_save.config(state=tk.NORMAL)

    # ----------------------------------------------------------
    # CSV 保存
    # ----------------------------------------------------------

    def _save_csv(self):
        if not self._trial_data:
            messagebox.showinfo("保存", "記録がありません。")
            return

        path = filedialog.asksaveasfilename(
            title="CSVファイルを保存",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="shikisai_result.csv",
        )
        if not path:
            return  # キャンセル

        fieldnames = ["trial", "color1", "color2",
                      "correct_ans", "user_ans", "is_correct", "rt_ms",
                      "brightness"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self._trial_data)
            messagebox.showinfo("保存完了", f"保存しました:\n{path}")
        except OSError as e:
            messagebox.showerror("保存エラー", str(e))

    # ----------------------------------------------------------
    # 終了処理
    # ----------------------------------------------------------

    def _on_close(self):
        if self._trial_data:
            ans = messagebox.askyesnocancel(
                "終了確認",
                "記録が保存されていません。\nCSVを保存してから終了しますか？"
            )
            if ans is None:   # キャンセル → 終了しない
                return
            if ans:           # はい → 保存ダイアログ
                self._save_csv()

        if self._serial and self._serial.is_open:
            try:
                self._send_command("OFF")
                self._serial.close()
            except Exception:
                pass
        self.destroy()


# ============================================================

if __name__ == "__main__":
    app = ExperimentApp()
    app.mainloop()
