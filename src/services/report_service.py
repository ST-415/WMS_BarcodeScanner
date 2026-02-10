#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report Service
Handles report generation and data processing
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date
import pandas as pd
from database.database_manager import DatabaseManager


class ReportService:
    """บริการจัดการรายงาน"""
    
    def __init__(self, context: str = "Service: ReportService"):
        self.db = DatabaseManager.get_instance(None, context)
    
    def generate_report(self, report_date: Optional[str] = None, job_id: Optional[int] = None, sub_job_id: Optional[int] = None,
                       note_filter: str = None, barcode_filter: str = None) -> Dict[str, Any]:
        """สร้างรายงาน"""
        try:

            # Get job type info (optional now)
            job_info = None
            if job_id:
                job_info = self.get_job_info(job_id)
                if not job_info:
                    return {'success': False, 'message': 'ไม่พบข้อมูลงานหลัก'}

            sub_job_info = None
            if sub_job_id:
                sub_job_info = self.get_sub_job_info(sub_job_id)
                if not sub_job_info:
                    return {'success': False, 'message': 'ไม่พบข้อมูลงานรอง'}

            # Build and execute query
            report_data = self.execute_report_query(report_date, job_id, sub_job_id, note_filter, barcode_filter)

            # Create summary
            summary = {
                'report_date': report_date if report_date else 'ทุกวัน',
                'job_type_name': job_info['job_name'] if job_info else 'ทั้งหมด',
                'sub_job_type_name': sub_job_info['sub_job_name'] if sub_job_info else 'ทั้งหมด',
                'barcode_filter': barcode_filter.strip() if barcode_filter and barcode_filter.strip() else None,
                'note_filter': note_filter.strip() if note_filter and note_filter.strip() else None,
                'total_count': len(report_data),
                'generated_at': datetime.now().isoformat()
            }

            return {
                'success': True,
                'summary': summary,
                'data': report_data
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการสร้างรายงาน: {str(e)}'
            }
    
    def execute_report_query(self, report_date: Optional[str] = None, job_id: Optional[int] = None,
                           sub_job_id: Optional[int] = None, note_filter: str = None,
                           barcode_filter: str = None) -> List[Dict[str, Any]]:
        """ดำเนินการ query สำหรับรายงาน"""
        try:
            query = """
                SELECT
                    sl.barcode,
                    sl.scan_date,
                    sl.notes,
                    sl.user_id,
                    ISNULL(jt.job_name, 'ไม่มี') as job_type_name,
                    ISNULL(sjt.sub_job_name, 'ไม่มี') as sub_job_type_name
                FROM scan_logs sl
                LEFT JOIN job_types jt ON sl.job_id = jt.id
                LEFT JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
                WHERE 1=1
            """
            params = []

            # Add date filter (optional)
            if report_date:
                query += " AND CAST(sl.scan_date AS DATE) = ?"
                params.append(report_date)

            # Add job type filter (optional)
            if job_id:
                query += " AND sl.job_id = ?"
                params.append(job_id)

            # Add sub job type filter
            if sub_job_id:
                query += " AND sl.sub_job_id = ?"
                params.append(sub_job_id)

            # Add barcode filter
            if barcode_filter and barcode_filter.strip():
                query += " AND sl.barcode LIKE ?"
                params.append(f"%{barcode_filter.strip()}%")

            # Add note filter
            if note_filter and note_filter.strip():
                query += " AND sl.notes LIKE ?"
                params.append(f"%{note_filter.strip()}%")

            query += " ORDER BY sl.scan_date DESC"

            results = self.db.execute_query(query, tuple(params))

            # Convert to list of dictionaries
            report_data = []
            for row in results:
                report_data.append({
                    'barcode': row['barcode'],
                    'scan_date': row['scan_date'],
                    'notes': row['notes'] or '',
                    'user_id': row['user_id'],
                    'job_type_name': row['job_type_name'],
                    'sub_job_type_name': row['sub_job_type_name']
                })

            return report_data

        except Exception as e:
            print(f"Error executing report query: {str(e)}")
            return []
    
    def get_job_info(self, job_id: int) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลงานหลัก"""
        try:
            query = "SELECT id, job_name FROM job_types WHERE id = ?"
            results = self.db.execute_query(query, (job_id,))
            
            if results:
                return results[0]
            
            return None
            
        except Exception as e:
            print(f"Error getting job info: {str(e)}")
            return None
    
    def get_sub_job_info(self, sub_job_id: int) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลงานรอง"""
        try:
            query = "SELECT id, sub_job_name FROM sub_job_types WHERE id = ?"
            results = self.db.execute_query(query, (sub_job_id,))
            
            if results:
                return results[0]
            
            return None
            
        except Exception as e:
            print(f"Error getting sub job info: {str(e)}")
            return None
    
    
    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """ดึงสรุปรายเดือน"""
        try:
            query = """
                SELECT 
                    jt.job_name,
                    COUNT(*) as scan_count,
                    COUNT(DISTINCT sl.barcode) as unique_barcode_count,
                    COUNT(DISTINCT sl.user_id) as user_count
                FROM scan_logs sl
                LEFT JOIN job_types jt ON sl.job_id = jt.id
                WHERE YEAR(sl.scan_date) = ? AND MONTH(sl.scan_date) = ?
                GROUP BY jt.job_name
                ORDER BY scan_count DESC
            """
            
            results = self.db.execute_query(query, (year, month))
            
            summary = []
            total_scans = 0
            total_unique_barcodes = 0
            
            for row in results:
                summary.append({
                    'job_name': row['job_name'] or 'ไม่ระบุ',
                    'scan_count': row['scan_count'],
                    'unique_barcode_count': row['unique_barcode_count'],
                    'user_count': row['user_count']
                })
                total_scans += row['scan_count']
                total_unique_barcodes += row['unique_barcode_count']
            
            return {
                'success': True,
                'data': {
                    'year': year,
                    'month': month,
                    'total_scans': total_scans,
                    'total_unique_barcodes': total_unique_barcodes,
                    'job_summary': summary
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการดึงสรุปรายเดือน: {str(e)}'
            }
    
    def get_user_activity_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """ดึงรายงานกิจกรรมผู้ใช้"""
        try:
            query = """
                SELECT 
                    sl.user_id,
                    COUNT(*) as total_scans,
                    COUNT(DISTINCT sl.barcode) as unique_barcodes,
                    COUNT(DISTINCT CAST(sl.scan_date AS DATE)) as active_days,
                    MIN(sl.scan_date) as first_scan,
                    MAX(sl.scan_date) as last_scan
                FROM scan_logs sl
                WHERE CAST(sl.scan_date AS DATE) BETWEEN ? AND ?
                GROUP BY sl.user_id
                ORDER BY total_scans DESC
            """
            
            results = self.db.execute_query(query, (start_date, end_date))
            
            activity_report = []
            for row in results:
                activity_report.append({
                    'user_id': row['user_id'],
                    'total_scans': row['total_scans'],
                    'unique_barcodes': row['unique_barcodes'],
                    'active_days': row['active_days'],
                    'first_scan': row['first_scan'],
                    'last_scan': row['last_scan']
                })
            
            return {
                'success': True,
                'data': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'user_activities': activity_report
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการดึงรายงานกิจกรรม: {str(e)}'
            }