#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan Service
Handles scanning business logic and data processing
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date
from database.database_manager import DatabaseManager
from services.job_service import JobService
from services.audit_service import AuditService
from services.sound_service import SoundService
from services.notification_service import NotificationService


class ScanService:
    """บริการจัดการการสแกน"""

    def __init__(self, context: str = "Service: ScanService"):
        self.db = DatabaseManager.get_instance(None, context)
        self.job_service = JobService("Service: JobService (via ScanService)")
        self.audit_service = AuditService("Service: AuditService (via ScanService)")
        self.sound_service = SoundService("Service: SoundService (via ScanService)")
        self.notification_service = NotificationService("Service: NotificationService (via ScanService)")
    
    def process_scan(self, barcode: str, job_id: int, sub_job_id: Optional[int] = None,
                    notes: str = None, user_id: str = None) -> Dict[str, Any]:
        """ประมวลผลการสแกนบาร์โค้ด"""
        try:
            # Validate inputs
            if not barcode or not barcode.strip():
                error_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'error')
                return {
                    'success': False,
                    'message': 'บาร์โค้ดไม่สามารถเป็นค่าว่างได้',
                    'sound': error_sound
                }

            if not job_id:
                error_sound = self.sound_service.get_sound_for_event(None, None, 'error')
                return {
                    'success': False,
                    'message': 'กรุณาเลือกประเภทงาน',
                    'sound': error_sound
                }

            barcode = barcode.strip()

            # Check job dependencies
            dep_result = self.job_service.check_job_dependencies(barcode, job_id)
            if not dep_result['success']:
                error_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'error')
                dep_result['sound'] = error_sound
                return dep_result

            # Check for notification popup BEFORE duplicate check
            # ใช้แบบพิจารณา job_id/sub_job_id เพื่อไม่ให้เตือนในงานที่ไม่ได้ระบุ
            notification = self.notification_service.get_notification_for_barcode_with_job(barcode, job_id, sub_job_id)
            notification_data = None
            if notification:
                notification_data = {
                    'barcode': barcode,
                    'title': notification['title'],
                    'message': notification['message'],
                    'note_fill': notification.get('note_fill'),
                    'event_type': notification['event_type'],
                    'popup_type': notification['popup_type']
                }

            # Check for duplicates
            dup_result = self.check_duplicate_scan(barcode, job_id, sub_job_id)
            if not dup_result['success']:
                # Add notification if exists (so it shows even for duplicates)
                if notification_data:
                    # Override sound with notification event_type if notification exists
                    notification_sound = self.sound_service.get_sound_for_event(
                        job_id, sub_job_id, notification_data['event_type']
                    )
                    dup_result['sound'] = notification_sound
                    dup_result['notification'] = notification_data
                else:
                    # Add duplicate sound only if no notification
                    duplicate_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'duplicate')
                    dup_result['sound'] = duplicate_sound
                return dup_result

            # Get job type name
            job_type_name = self.get_job_type_name(job_id)
            if not job_type_name:
                error_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'error')
                return {
                    'success': False,
                    'message': 'ไม่พบข้อมูลประเภทงาน',
                    'sound': error_sound
                }

            # Get sub job type name if sub_job_id exists
            sub_job_type_name = None
            if sub_job_id:
                sub_job_type_name = self.get_sub_job_type_name(sub_job_id)

            # Auto-append note_fill from notification to notes if exists
            final_notes = notes or ''
            if notification and notification.get('note_fill'):
                note_fill = notification['note_fill'].strip()
                if note_fill:
                    if final_notes:
                        # Append note_fill with comma separator
                        final_notes = f"{final_notes},{note_fill}"
                    else:
                        # Use note_fill only
                        final_notes = note_fill

            # Save scan record
            save_result = self.save_scan_record(barcode, job_id, sub_job_id, job_type_name, sub_job_type_name, final_notes, user_id)

            # Add success sound if save was successful
            if save_result.get('success'):
                # Add notification if exists
                if notification_data:
                    # Override sound with notification event_type if notification exists
                    notification_sound = self.sound_service.get_sound_for_event(
                        job_id, sub_job_id, notification_data['event_type']
                    )
                    save_result['sound'] = notification_sound
                    save_result['notification'] = notification_data
                else:
                    # Use success sound if no notification
                    success_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'success')
                    save_result['sound'] = success_sound
            else:
                error_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'error')
                save_result['sound'] = error_sound

            return save_result

        except Exception as e:
            error_sound = self.sound_service.get_sound_for_event(job_id, sub_job_id, 'error')
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาด: {str(e)}',
                'sound': error_sound
            }
    
    def check_duplicate_scan(self, barcode: str, job_id: int, sub_job_id: Optional[int] = None) -> Dict[str, Any]:
        """ตรวจสอบการสแกนซ้ำ"""
        try:
            if sub_job_id:
                # Check for specific sub job type
                query = """
                    SELECT sl.*, jt.job_name, sjt.sub_job_name
                    FROM scan_logs sl
                    LEFT JOIN job_types jt ON sl.job_id = jt.id
                    LEFT JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
                    WHERE sl.barcode = ? AND sl.job_id = ? AND sl.sub_job_id = ?
                    ORDER BY sl.scan_date DESC
                """
                results = self.db.execute_query(query, (barcode, job_id, sub_job_id))
            else:
                # Check for main job only (no sub job)
                query = """
                    SELECT sl.*, jt.job_name, sjt.sub_job_name
                    FROM scan_logs sl
                    LEFT JOIN job_types jt ON sl.job_id = jt.id
                    LEFT JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
                    WHERE sl.barcode = ? AND sl.job_id = ? AND sl.sub_job_id IS NULL
                    ORDER BY sl.scan_date DESC
                """
                results = self.db.execute_query(query, (barcode, job_id))
            
            if results:
                existing_record = results[0]
                job_display = existing_record['job_name'] or existing_record.get('job_type', '')
                sub_job_display = existing_record.get('sub_job_name') or 'ไม่มี'
                
                # Format scan_date to a human-friendly string (avoid 'T' and microseconds)
                try:
                    scan_dt = existing_record['scan_date']
                    if hasattr(scan_dt, 'strftime'):
                        formatted_scan_date = scan_dt.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        # Fallback if value is already a string
                        formatted_scan_date = str(scan_dt).replace('T', ' ').split('.')[0]
                except Exception:
                    formatted_scan_date = str(existing_record.get('scan_date', ''))

                return {
                    'success': False,
                    'message': f'บาร์โค้ด {barcode} ถูกสแกนในงาน "{job_display} > {sub_job_display}" แล้ว',
                    'duplicate': True,
                    'existing_record': {
                        'scan_date': formatted_scan_date,
                        'job_type_name': job_display,
                        'sub_job_type_name': sub_job_display,
                        'user_id': existing_record['user_id']
                    }
                }
            
            return {'success': True, 'message': 'ไม่พบการสแกนซ้ำ'}
            
        except Exception as e:
            return {'success': False, 'message': f'เกิดข้อผิดพลาดในการตรวจสอบการสแกนซ้ำ: {str(e)}'}
    
    def save_scan_record(self, barcode: str, job_id: int, sub_job_id: Optional[int],
                        job_type_name: str, sub_job_type_name: Optional[str] = None,
                        notes: str = None, user_id: str = None) -> Dict[str, Any]:
        """บันทึกข้อมูลการสแกน"""
        try:
            # Get current user if not provided
            if not user_id:
                user_id = self.db.current_user or 'system'

            # Clean notes
            clean_notes = notes.strip() if notes else None

            # Insert record
            query = """
                INSERT INTO scan_logs (barcode, scan_date, job_type, sub_job_type, user_id, job_id, sub_job_id, notes)
                VALUES (?, GETDATE(), ?, ?, ?, ?, ?, ?)
            """

            rows_affected = self.db.execute_non_query(query, (
                barcode, job_type_name, sub_job_type_name, user_id, job_id, sub_job_id, clean_notes
            ))
            
            if rows_affected > 0:
                return {
                    'success': True,
                    'message': f'บันทึกการสแกนบาร์โค้ด {barcode} สำเร็จ'
                }
            else:
                return {
                    'success': False,
                    'message': 'ไม่สามารถบันทึกข้อมูลได้'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการบันทึก: {str(e)}'
            }
    
    def get_job_type_name(self, job_id: int) -> Optional[str]:
        """ดึงชื่อประเภทงานจาก ID"""
        try:
            query = "SELECT job_name FROM job_types WHERE id = ?"
            results = self.db.execute_query(query, (job_id,))

            if results:
                return results[0]['job_name']

            return None

        except Exception as e:
            print(f"Error getting job type name: {str(e)}")
            return None

    def get_sub_job_type_name(self, sub_job_id: int) -> Optional[str]:
        """ดึงชื่อประเภทงานย่อยจาก ID"""
        try:
            query = "SELECT sub_job_name FROM sub_job_types WHERE id = ?"
            results = self.db.execute_query(query, (sub_job_id,))

            if results:
                return results[0]['sub_job_name']

            return None

        except Exception as e:
            print(f"Error getting sub job type name: {str(e)}")
            return None

    def get_scan_history(self, limit: int = 50, date_filter: str = None, 
                        job_id: int = None, sub_job_id: int = None, 
                        barcode_filter: str = None, notes_filter: str = None,
                        today_only: bool = True) -> List[Dict[str, Any]]:
        """ดึงประวัติการสแกน"""
        try:
            query = """
                SELECT TOP (?) 
                    sl.id,
                    sl.barcode,
                    sl.scan_date,
                    jt.job_name as job_type_name,
                    ISNULL(sjt.sub_job_name, 'ไม่มี') as sub_job_type_name,
                    sl.notes,
                    sl.user_id,
                    CASE 
                        WHEN sl.scan_date >= DATEADD(MINUTE, -5, GETDATE()) THEN 'ใหม่'
                        ELSE 'ปกติ'
                    END as status
                FROM scan_logs sl
                LEFT JOIN job_types jt ON sl.job_id = jt.id
                LEFT JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
                WHERE 1=1
            """
            
            params = [limit]
            
            # Add today filter if enabled (default behavior)
            if today_only:
                query += " AND CAST(sl.scan_date AS DATE) = CAST(GETDATE() AS DATE)"
            
            # Add specific date filter (overrides today_only if provided)
            if date_filter:
                query += " AND CAST(sl.scan_date AS DATE) = ?"
                params.append(date_filter)
            
            # Add job filter
            if job_id:
                query += " AND sl.job_id = ?"
                params.append(job_id)
            
            # Add sub job filter
            if sub_job_id:
                query += " AND sl.sub_job_id = ?"
                params.append(sub_job_id)
            
            # Add barcode filter
            if barcode_filter:
                query += " AND sl.barcode LIKE ?"
                params.append(f"%{barcode_filter}%")
            
            # Add notes filter
            if notes_filter:
                query += " AND sl.notes LIKE ?"
                params.append(f"%{notes_filter}%")
            
            query += " ORDER BY sl.scan_date DESC"
            
            results = self.db.execute_query(query, tuple(params))
            
            history = []
            for row in results:
                history.append({
                    'id': row['id'],
                    'barcode': row['barcode'],
                    'scan_date': row['scan_date'],
                    'job_type_name': row['job_type_name'],
                    'sub_job_type_name': row['sub_job_type_name'],
                    'notes': row['notes'] or '',
                    'user_id': row['user_id'],
                    'status': row['status']
                })
            
            return history
            
        except Exception as e:
            print(f"Error getting scan history: {str(e)}")
            return []
    
    def get_today_summary(self, job_id: int, sub_job_id: Optional[int] = None, 
                         notes_filter: str = None) -> Dict[str, Any]:
        """ดึงสรุปการสแกนวันนี้"""
        try:
            # Build query
            if sub_job_id:
                query = """
                    SELECT COUNT(*) as total_count
                    FROM scan_logs sl
                    WHERE sl.job_id = ? 
                    AND sl.sub_job_id = ?
                    AND CAST(sl.scan_date AS DATE) = CAST(GETDATE() AS DATE)
                """
                params = [job_id, sub_job_id]
            else:
                query = """
                    SELECT COUNT(*) as total_count
                    FROM scan_logs sl
                    WHERE sl.job_id = ? 
                    AND CAST(sl.scan_date AS DATE) = CAST(GETDATE() AS DATE)
                """
                params = [job_id]
            
            # Add notes filter
            if notes_filter and notes_filter.strip():
                query += " AND sl.notes LIKE ?"
                params.append(f"%{notes_filter.strip()}%")
            
            results = self.db.execute_query(query, tuple(params))
            total_count = results[0]['total_count'] if results else 0
            
            # Get job type info
            job_query = "SELECT job_name FROM job_types WHERE id = ?"
            job_result = self.db.execute_query(job_query, (job_id,))
            job_type_name = job_result[0]['job_name'] if job_result else 'ไม่ทราบ'
            
            sub_job_type_name = 'ไม่มี'
            if sub_job_id:
                sub_job_query = "SELECT sub_job_name FROM sub_job_types WHERE id = ?"
                sub_job_result = self.db.execute_query(sub_job_query, (sub_job_id,))
                if sub_job_result:
                    sub_job_type_name = sub_job_result[0]['sub_job_name']
            
            return {
                'success': True,
                'data': {
                    'total_count': total_count,
                    'job_type_name': job_type_name,
                    'sub_job_type_name': sub_job_type_name,
                    'note_filter': notes_filter.strip() if notes_filter and notes_filter.strip() else None,
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการดึงสรุป: {str(e)}'
            }
    
    def update_scan_record(self, record_id: int, notes: str = None, barcode: str = None, 
                          job_id: int = None, sub_job_id: int = None, user_id: str = None) -> Dict[str, Any]:
        """อัปเดตข้อมูลการสแกน"""
        try:
            # Get old values before update for audit log
            old_query = """
                SELECT sl.*, jt.job_name, sjt.sub_job_name
                FROM scan_logs sl
                LEFT JOIN job_types jt ON sl.job_id = jt.id
                LEFT JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
                WHERE sl.id = ?
            """
            old_data = self.db.execute_query(old_query, (record_id,))
            
            if not old_data:
                return {
                    'success': False,
                    'message': 'ไม่พบข้อมูลที่ต้องการอัปเดต'
                }
            
            old_record = old_data[0]
            
            # Create old values dict for audit
            old_values = {
                'id': old_record['id'],
                'barcode': old_record['barcode'],
                'scan_date': old_record['scan_date'].isoformat() if old_record['scan_date'] else None,
                'job_type': old_record.get('job_name') or old_record['job_type'],
                'sub_job_type': old_record.get('sub_job_name') or 'ไม่มี',
                'notes': old_record['notes'] or '',
                'user_id': old_record['user_id']
            }
            
            # Build update query and params based on what needs to be updated
            update_fields = []
            params = []
            
            if barcode is not None:
                update_fields.append("barcode = ?")
                params.append(barcode.strip())
            
            if job_id is not None:
                # Get job type name
                job_name = self.get_job_type_name(job_id)
                if job_name:
                    update_fields.append("job_type = ?")
                    update_fields.append("job_id = ?")
                    params.extend([job_name, job_id])

            if sub_job_id is not None:
                # Get sub job type name
                sub_job_name = None
                if sub_job_id:
                    sub_job_name = self.get_sub_job_type_name(sub_job_id)

                update_fields.append("sub_job_type = ?")
                update_fields.append("sub_job_id = ?")
                params.extend([sub_job_name, sub_job_id])
            
            if notes is not None:
                clean_notes = notes.strip() if notes else None
                update_fields.append("notes = ?")
                params.append(clean_notes)
            
            if not update_fields:
                return {
                    'success': False,
                    'message': 'ไม่มีข้อมูลที่ต้องการอัปเดต'
                }
            
            # Update the record
            query = f"UPDATE scan_logs SET {', '.join(update_fields)} WHERE id = ?"
            params.append(record_id)
            rows_affected = self.db.execute_non_query(query, tuple(params))
            
            if rows_affected > 0:
                # Create new values dict for audit
                new_values = old_values.copy()
                
                # Update new values with changes
                if barcode is not None:
                    new_values['barcode'] = barcode.strip()
                if job_id is not None and job_name:
                    new_values['job_type'] = job_name
                if sub_job_id is not None:
                    # Get sub job type name if provided
                    if sub_job_id:
                        sub_query = "SELECT sub_job_name FROM sub_job_types WHERE id = ?"
                        sub_result = self.db.execute_query(sub_query, (sub_job_id,))
                        new_values['sub_job_type'] = sub_result[0]['sub_job_name'] if sub_result else 'ไม่มี'
                    else:
                        new_values['sub_job_type'] = 'ไม่มี'
                if notes is not None:
                    new_values['notes'] = clean_notes or ''
                
                # Log the audit change
                audit_user = user_id or self.db.current_user or 'system'
                self.audit_service.log_scan_change(
                    scan_record_id=record_id,
                    action_type='UPDATE',
                    old_values=old_values,
                    new_values=new_values,
                    changed_by=audit_user,
                    notes='แก้ไขงานรองหรือหมายเหตุ'
                )
                
                return {
                    'success': True,
                    'message': 'อัปเดตข้อมูลสำเร็จ'
                }
            else:
                return {
                    'success': False,
                    'message': 'ไม่พบข้อมูลที่ต้องการอัปเดต'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการอัปเดต: {str(e)}'
            }
    
    def delete_scan_record(self, record_id: int, user_id: str = None) -> Dict[str, Any]:
        """ลบข้อมูลการสแกน"""
        try:
            # Get record data before deletion for audit log
            old_query = """
                SELECT sl.*, jt.job_name, sjt.sub_job_name
                FROM scan_logs sl
                LEFT JOIN job_types jt ON sl.job_id = jt.id
                LEFT JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
                WHERE sl.id = ?
            """
            old_data = self.db.execute_query(old_query, (record_id,))
            
            if not old_data:
                return {
                    'success': False,
                    'message': 'ไม่พบข้อมูลที่ต้องการลบ'
                }
            
            old_record = old_data[0]

            # ตรวจสอบว่ามีงานที่ตามหลัง (dependent jobs) สำหรับบาร์โค้ดนี้หรือไม่
            # โครงสร้าง: job_dependencies(job_id, required_job_id)
            # ถ้าพบว่ามีการสแกนงานที่ job_id ∈ (SELECT job_id FROM job_dependencies WHERE required_job_id = old_record.job_id)
            # และใช้ barcode เดียวกัน ให้บล็อกการลบ
            try:
                dep_check_query = """
                    SELECT COUNT(*) AS count
                    FROM scan_logs sl
                    WHERE sl.barcode = ? AND sl.job_id IN (
                        SELECT jd.job_id FROM job_dependencies jd WHERE jd.required_job_id = ?
                    )
                """
                dep_result = self.db.execute_query(dep_check_query, (old_record['barcode'], old_record['job_id']))
                if dep_result and dep_result[0]['count'] > 0:
                    return {
                        'success': False,
                        'message': 'ไม่สามารถลบได้ เนื่องจากมีงานถัดไปที่อ้างอิงงานนี้อยู่'
                    }
            except Exception as dep_err:
                # หากตรวจสอบไม่สำเร็จ (เช่น ไม่มีตาราง job_dependencies) ให้ถือว่าไม่มีการพึ่งพาและอนุญาตให้ลบต่อไป
                pass
            
            # Create old values dict for audit
            old_values = {
                'id': old_record['id'],
                'barcode': old_record['barcode'],
                'scan_date': old_record['scan_date'].isoformat() if old_record['scan_date'] else None,
                'job_type': old_record.get('job_name') or old_record['job_type'],
                'sub_job_type': old_record.get('sub_job_name') or 'ไม่มี',
                'notes': old_record['notes'] or '',
                'user_id': old_record['user_id']
            }
            
            # Delete the record
            query = "DELETE FROM scan_logs WHERE id = ?"
            rows_affected = self.db.execute_non_query(query, (record_id,))
            
            if rows_affected > 0:
                # Log the audit change
                audit_user = user_id or self.db.current_user or 'system'
                self.audit_service.log_scan_change(
                    scan_record_id=record_id,
                    action_type='DELETE',
                    old_values=old_values,
                    new_values=None,
                    changed_by=audit_user,
                    notes='ลบข้อมูลการสแกน'
                )
                
                return {
                    'success': True,
                    'message': 'ลบข้อมูลสำเร็จ'
                }
            else:
                return {
                    'success': False,
                    'message': 'ไม่พบข้อมูลที่ต้องการลบ'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'เกิดข้อผิดพลาดในการลบ: {str(e)}'
            }