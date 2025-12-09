#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanning Tab Component
UI component for barcode scanning
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Callable
from datetime import datetime


class ScanningTab:
    """แท็บการสแกนบาร์โค้ด"""
    
    def __init__(self, parent: ttk.Frame, db_manager, on_scan_completed: Callable = None):
        self.parent = parent
        self.db_manager = db_manager
        self.on_scan_completed = on_scan_completed
        
        self.setup_ui()
        self.refresh_job_types()
    
    def setup_ui(self):
        """สร้าง UI"""
        # สร้าง frame หลัก
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # หัวข้อ
        title_label = ttk.Label(main_frame, text="สแกนบาร์โค้ด", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame สำหรับการสแกน
        scan_frame = ttk.LabelFrame(main_frame, text="การสแกน")
        scan_frame.pack(fill=tk.X, pady=(0, 20))
        
        # เลือก Job Type
        ttk.Label(scan_frame, text="Job Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.job_type_var = tk.StringVar()
        self.job_type_combo = ttk.Combobox(scan_frame, textvariable=self.job_type_var, 
                                          state="readonly", width=30)
        self.job_type_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.job_type_combo.bind("<<ComboboxSelected>>", self.on_job_type_change)
        
        # เลือก Sub Job Type
        ttk.Label(scan_frame, text="Sub Job Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.sub_job_type_var = tk.StringVar()
        self.sub_job_type_combo = ttk.Combobox(scan_frame, textvariable=self.sub_job_type_var, 
                                              state="readonly", width=30)
        self.sub_job_type_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Barcode Entry
        ttk.Label(scan_frame, text="Barcode:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.barcode_entry = ttk.Entry(scan_frame, width=40, font=("Arial", 12))
        self.barcode_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.barcode_entry.bind("<Return>", self.process_barcode)
        self.barcode_entry.focus_set()
        
        # ปุ่มสแกน
        scan_button = ttk.Button(scan_frame, text="สแกน", command=self.process_barcode)
        scan_button.grid(row=2, column=2, padx=5, pady=5)
        
        # Frame สำหรับประวัติการสแกน
        history_frame = ttk.LabelFrame(main_frame, text="ประวัติการสแกนล่าสุด")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Treeview สำหรับประวัติ
        columns = ("เวลา", "Barcode", "Job Type", "Sub Job Type", "สถานะ")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=150)
        
        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar สำหรับ Treeview
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        # Frame สำหรับปุ่ม
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="ล้างข้อมูล", command=self.clear_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="รีเฟรช", command=self.refresh_history).pack(side=tk.LEFT, padx=5)
        
        # โหลดประวัติเริ่มต้น
        self.refresh_history()
    
    def refresh_job_types(self):
        """รีเฟรชรายการ Job Types"""
        try:
            query = "SELECT id, name FROM job_types WHERE is_active = 1 ORDER BY name"
            results = self.db_manager.execute_query(query)
            
            job_types = [row['name'] for row in results]
            self.job_type_combo['values'] = job_types
            
            if job_types:
                self.job_type_combo.set(job_types[0])
                
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถโหลด Job Types: {str(e)}")
    
    def on_job_type_change(self, event=None):
        """เมื่อเปลี่ยน Job Type"""
        selected_job = self.job_type_var.get()
        if not selected_job:
            return
        
        try:
            # ดึง Job Type ID
            query = "SELECT id FROM job_types WHERE name = ?"
            result = self.db_manager.execute_query(query, (selected_job,))
            
            if result:
                job_type_id = result[0]['id']
                
                # ดึง Sub Job Types
                query = "SELECT id, name FROM sub_job_types WHERE main_job_id = ? AND is_active = 1 ORDER BY name"
                results = self.db_manager.execute_query(query, (job_type_id,))
                
                sub_job_types = [row['name'] for row in results]
                self.sub_job_type_combo['values'] = sub_job_types
                
                if sub_job_types:
                    self.sub_job_type_combo.set(sub_job_types[0])
                else:
                    self.sub_job_type_combo.set("")
                    
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถโหลด Sub Job Types: {str(e)}")
    
    def process_barcode(self, event=None):
        """ประมวลผลบาร์โค้ด"""
        barcode = self.barcode_entry.get().strip()
        job_type = self.job_type_var.get()
        sub_job_type = self.sub_job_type_var.get()
        
        if not barcode:
            messagebox.showwarning("คำเตือน", "กรุณากรอกบาร์โค้ด")
            return
        
        if not job_type:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Job Type")
            return
        
        try:
            # ตรวจสอบว่าบาร์โค้ดซ้ำหรือไม่
            query = """
                SELECT s.*, j.name as job_type_name, sj.name as sub_job_type_name
                FROM scan_logs s
                JOIN job_types j ON s.job_type_id = j.id
                LEFT JOIN sub_job_types sj ON s.sub_job_type_id = sj.id
                WHERE s.barcode = ? AND s.status = 'Active'
                ORDER BY s.scan_date DESC
            """
            existing_records = self.db_manager.execute_query(query, (barcode,))
            
            if existing_records:
                self.show_duplicate_warning(barcode, existing_records[0])
                return
            
            # ดึง Job Type ID
            query = "SELECT id FROM job_types WHERE name = ?"
            job_result = self.db_manager.execute_query(query, (job_type,))
            
            if not job_result:
                messagebox.showerror("ผิดพลาด", "ไม่พบ Job Type ที่เลือก")
                return
            
            job_type_id = job_result[0]['id']
            sub_job_type_id = None
            
            # ดึง Sub Job Type ID ถ้ามี
            if sub_job_type:
                query = "SELECT id FROM sub_job_types WHERE name = ? AND main_job_id = ?"
                sub_result = self.db_manager.execute_query(query, (sub_job_type, job_type_id))
                if sub_result:
                    sub_job_type_id = sub_result[0]['id']

            # บันทึกการสแกน (รวม job_type และ sub_job_type fields)
            query = """
                INSERT INTO scan_logs (barcode, job_id, sub_job_id, scan_date, job_type, sub_job_type, user_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            scan_date = datetime.now()
            self.db_manager.execute_non_query(query, (
                barcode, job_type_id, sub_job_type_id, scan_date, job_type, sub_job_type if sub_job_type else None,
                self.db_manager.current_user, ''
            ))
            
            # แสดงข้อความสำเร็จ
            messagebox.showinfo("สำเร็จ", f"บันทึกการสแกนบาร์โค้ด: {barcode}")
            
            # ล้างข้อมูล
            self.barcode_entry.delete(0, tk.END)
            self.barcode_entry.focus_set()
            
            # รีเฟรชประวัติ
            self.refresh_history()
            
            # เรียก callback
            if self.on_scan_completed:
                self.on_scan_completed()
                
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถบันทึกการสแกน: {str(e)}")
    
    def show_duplicate_warning(self, barcode: str, existing_record: Dict):
        """แสดงคำเตือนเมื่อบาร์โค้ดซ้ำ"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("บาร์โค้ดซ้ำ")
        dialog.geometry("500x300")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # สร้าง UI สำหรับ dialog
        ttk.Label(dialog, text=f"บาร์โค้ด {barcode} ถูกสแกนแล้ว", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        info_text = f"""
        ข้อมูลการสแกนก่อนหน้า:
        - Job Type: {existing_record['job_type_name']}
        - Sub Job Type: {existing_record['sub_job_type_name'] or 'ไม่มี'}
        - วันที่สแกน: {existing_record['scan_date']}
        - ผู้สแกน: {existing_record['scanned_by']}
        """
        
        text_widget = tk.Text(dialog, height=8, width=50)
        text_widget.pack(padx=10, pady=10)
        text_widget.insert(tk.END, info_text)
        text_widget.config(state=tk.DISABLED)
        
        def continue_scanning():
            dialog.destroy()
            self.barcode_entry.focus_set()
        
        ttk.Button(dialog, text="ตกลง", command=continue_scanning).pack(pady=10)
    
    def refresh_history(self):
        """รีเฟรชประวัติการสแกน"""
        # ล้างข้อมูลเก่า
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        try:
            # ดึงประวัติล่าสุด
            query = """
                SELECT s.*, j.name as job_type_name, sj.name as sub_job_type_name
                FROM scan_logs s
                JOIN job_types j ON s.job_type_id = j.id
                LEFT JOIN sub_job_types sj ON s.sub_job_type_id = sj.id
                WHERE s.status = 'Active'
                ORDER BY s.scan_date DESC
                LIMIT 50
            """
            results = self.db_manager.execute_query(query)
            
            for row in results:
                scan_time = row['scan_date'].strftime("%Y-%m-%d %H:%M:%S") if row['scan_date'] else ""
                sub_job = row['sub_job_type_name'] or ""
                status = "สำเร็จ" if row['status'] == 'Active' else row['status']
                
                self.history_tree.insert("", tk.END, values=(
                    scan_time, row['barcode'], row['job_type_name'], sub_job, status
                ))
                
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถโหลดประวัติ: {str(e)}")
    
    def clear_data(self):
        """ล้างข้อมูล"""
        if messagebox.askyesno("ยืนยัน", "คุณต้องการล้างข้อมูลการสแกนหรือไม่?"):
            self.barcode_entry.delete(0, tk.END)
            self.job_type_var.set("")
            self.sub_job_type_var.set("")
            self.barcode_entry.focus_set() 