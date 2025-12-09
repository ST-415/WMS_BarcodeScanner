#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import Tab Component
UI component for data import
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, Callable, List
import pandas as pd
from utils.file_utils import select_file, read_excel_file, create_template_excel
from utils.validation_utils import validate_import_data


class ImportTab:
    """แท็บการนำเข้าข้อมูล"""
    
    def __init__(self, parent: ttk.Frame, db_manager, on_import_completed: Callable = None):
        self.parent = parent
        self.db_manager = db_manager
        self.on_import_completed = on_import_completed
        self.import_data = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """สร้าง UI"""
        # สร้าง frame หลัก
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # หัวข้อ
        title_label = ttk.Label(main_frame, text="นำเข้าข้อมูล", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame สำหรับการเลือกไฟล์
        file_frame = ttk.LabelFrame(main_frame, text="เลือกไฟล์")
        file_frame.pack(fill=tk.X, pady=(0, 20))
        
        # ปุ่มเลือกไฟล์
        ttk.Button(file_frame, text="เลือกไฟล์ Excel/CSV", command=self.select_file).pack(side=tk.LEFT, padx=5, pady=10)
        
        # ปุ่มดาวน์โหลด template
        ttk.Button(file_frame, text="ดาวน์โหลด Template", command=self.download_template).pack(side=tk.LEFT, padx=5, pady=10)
        
        # แสดงชื่อไฟล์ที่เลือก
        self.file_label = ttk.Label(file_frame, text="ยังไม่ได้เลือกไฟล์")
        self.file_label.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Frame สำหรับการตรวจสอบข้อมูล
        preview_frame = ttk.LabelFrame(main_frame, text="ตรวจสอบข้อมูล")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Treeview สำหรับแสดงข้อมูล
        columns = ("แถว", "Barcode", "Job Type", "Sub Job Type", "หมายเหตุ", "สถานะ")
        self.preview_tree = ttk.Treeview(preview_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.preview_tree.heading(col, text=col)
            self.preview_tree.column(col, width=120)
        
        self.preview_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar สำหรับ Treeview
        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_tree.configure(yscrollcommand=scrollbar.set)
        
        # Frame สำหรับปุ่ม
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="ตรวจสอบข้อมูล", command=self.validate_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="นำเข้าข้อมูล", command=self.import_data_to_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="ล้างข้อมูล", command=self.clear_data).pack(side=tk.LEFT, padx=5)
    
    def select_file(self):
        """เลือกไฟล์"""
        file_path = select_file("เลือกไฟล์ Excel/CSV", [
            ("Excel files", "*.xlsx *.xls"),
            ("CSV files", "*.csv"),
            ("All files", "*.*")
        ])
        
        if file_path:
            self.file_label.config(text=f"ไฟล์: {file_path}")
            self.load_file(file_path)
    
    def load_file(self, file_path: str):
        """โหลดไฟล์"""
        try:
            self.import_data = read_excel_file(file_path)
            
            if self.import_data is not None:
                self.display_preview()
            else:
                messagebox.showerror("ผิดพลาด", "ไม่สามารถอ่านไฟล์ได้")
                
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"เกิดข้อผิดพลาดในการโหลดไฟล์: {str(e)}")
    
    def display_preview(self):
        """แสดงตัวอย่างข้อมูล"""
        # ล้างข้อมูลเก่า
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        if self.import_data is None or self.import_data.empty:
            return
        
        # แสดงข้อมูล 20 แถวแรก
        preview_data = self.import_data.head(20)
        
        for index, row in preview_data.iterrows():
            barcode = str(row.get('barcode', '')) if pd.notna(row.get('barcode')) else ''
            job_type = str(row.get('job_type', '')) if pd.notna(row.get('job_type')) else ''
            sub_job_type = str(row.get('sub_job_type', '')) if pd.notna(row.get('sub_job_type')) else ''
            notes = str(row.get('notes', '')) if pd.notna(row.get('notes')) else ''
            
            # Clean up display values to avoid showing 'nan'
            barcode = barcode.replace('nan', '').replace('None', '')
            job_type = job_type.replace('nan', '').replace('None', '')
            sub_job_type = sub_job_type.replace('nan', '').replace('None', '')
            notes = notes.replace('nan', '').replace('None', '')
            
            self.preview_tree.insert("", tk.END, values=(
                index + 1, barcode, job_type, sub_job_type, notes, "รอตรวจสอบ"
            ))
    
    def download_template(self):
        """ดาวน์โหลด template"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="บันทึก Template",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")]
            )
            
            if file_path:
                columns = ["barcode", "job_type", "sub_job_type", "notes"]
                sample_data = [
                    ["ABC123", "Receiving", "Quality Check", "ตัวอย่างข้อมูล"],
                    ["DEF456", "Picking", "Packaging", "ตัวอย่างข้อมูล"]
                ]
                
                if create_template_excel(file_path, columns, sample_data):
                    messagebox.showinfo("สำเร็จ", f"บันทึก template เรียบร้อยแล้วที่: {file_path}")
                else:
                    messagebox.showerror("ผิดพลาด", "ไม่สามารถสร้าง template ได้")
                    
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"เกิดข้อผิดพลาด: {str(e)}")
    
    def validate_data(self):
        """ตรวจสอบข้อมูล"""
        if self.import_data is None:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกไฟล์ก่อน")
            return
        
        try:
            required_columns = ["barcode", "job_type"]
            is_valid, errors = validate_import_data(self.import_data, required_columns)
            
            if is_valid:
                messagebox.showinfo("สำเร็จ", "ข้อมูลถูกต้อง สามารถนำเข้าได้")
                self.update_preview_status("ผ่าน")
            else:
                error_message = "\n".join(errors[:10])  # แสดง 10 ข้อผิดพลาดแรก
                if len(errors) > 10:
                    error_message += f"\n... และอีก {len(errors) - 10} ข้อผิดพลาด"
                
                messagebox.showerror("ข้อผิดพลาด", f"พบข้อผิดพลาดในข้อมูล:\n{error_message}")
                self.update_preview_status("ไม่ผ่าน")
                
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"เกิดข้อผิดพลาดในการตรวจสอบ: {str(e)}")
    
    def update_preview_status(self, status: str):
        """อัปเดตสถานะใน preview"""
        for item in self.preview_tree.get_children():
            values = list(self.preview_tree.item(item)['values'])
            values[-1] = status
            self.preview_tree.item(item, values=values)
    
    def import_data_to_db(self):
        """นำเข้าข้อมูลลงฐานข้อมูล"""
        if self.import_data is None:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกไฟล์ก่อน")
            return
        
        if not messagebox.askyesno("ยืนยัน", "คุณต้องการนำเข้าข้อมูลหรือไม่?"):
            return
        
        try:
            success_count = 0
            error_count = 0
            
            for index, row in self.import_data.iterrows():
                try:
                    barcode = str(row.get('barcode', '')).strip()
                    job_type = str(row.get('job_type', '')).strip()
                    sub_job_type = str(row.get('sub_job_type', '')).strip() if pd.notna(row.get('sub_job_type')) else None
                    notes = str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else ''
                    
                    # Clean up values to avoid 'nan' strings
                    barcode = barcode.replace('nan', '').replace('None', '')
                    job_type = job_type.replace('nan', '').replace('None', '')
                    if sub_job_type:
                        sub_job_type = sub_job_type.replace('nan', '').replace('None', '')
                    notes = notes.replace('nan', '').replace('None', '')
                    
                    if not barcode or not job_type:
                        error_count += 1
                        continue
                    
                    # ดึง Job Type ID
                    query = "SELECT id FROM job_types WHERE name = ?"
                    job_result = self.db_manager.execute_query(query, (job_type,))
                    
                    if not job_result:
                        error_count += 1
                        continue
                    
                    job_type_id = job_result[0]['id']
                    sub_job_type_id = None
                    
                    # ดึง Sub Job Type ID ถ้ามี
                    if sub_job_type:
                        query = "SELECT id FROM sub_job_types WHERE name = ? AND main_job_id = ?"
                        sub_result = self.db_manager.execute_query(query, (sub_job_type, job_type_id))
                        if sub_result:
                            sub_job_type_id = sub_result[0]['id']

                    # Prepare notes with "import" prefix
                    if notes:
                        formatted_notes = f"import {notes}"
                    else:
                        formatted_notes = "import"

                    # บันทึกข้อมูล (รวม job_type และ sub_job_type fields)
                    query = """
                        INSERT INTO scan_logs (barcode, job_id, sub_job_id, scan_date, job_type, sub_job_type, user_id, notes)
                        VALUES (?, ?, ?, GETDATE(), ?, ?, ?, ?)
                    """
                    self.db_manager.execute_non_query(query, (
                        barcode, job_type_id, sub_job_type_id, job_type, sub_job_type if sub_job_type else None,
                        self.db_manager.current_user, formatted_notes
                    ))
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    print(f"Error importing row {index + 1}: {str(e)}")
            
            messagebox.showinfo("เสร็จสิ้น", f"นำเข้าข้อมูลเสร็จสิ้น\nสำเร็จ: {success_count} รายการ\nผิดพลาด: {error_count} รายการ")
            
            # เรียก callback
            if self.on_import_completed:
                self.on_import_completed()
                
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"เกิดข้อผิดพลาดในการนำเข้าข้อมูล: {str(e)}")
    
    def clear_data(self):
        """ล้างข้อมูล"""
        if messagebox.askyesno("ยืนยัน", "คุณต้องการล้างข้อมูลหรือไม่?"):
            self.import_data = None
            self.file_label.config(text="ยังไม่ได้เลือกไฟล์")
            
            # ล้าง preview
            for item in self.preview_tree.get_children():
                self.preview_tree.delete(item) 