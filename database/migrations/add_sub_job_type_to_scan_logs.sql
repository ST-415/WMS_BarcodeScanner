-- ===========================================
-- Migration: Add sub_job_type column to scan_logs
-- Date: 2025-12-09
-- Description: เพิ่ม column sub_job_type เพื่อเก็บชื่อประเภทงานย่อยแบบ denormalized (เหมือนกับ job_type)
-- ===========================================

USE WMS_EP;
GO

-- ตรวจสอบว่า column sub_job_type มีอยู่แล้วหรือไม่
IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'scan_logs'
    AND COLUMN_NAME = 'sub_job_type'
)
BEGIN
    PRINT 'Adding sub_job_type column to scan_logs table...';

    -- เพิ่ม column sub_job_type
    ALTER TABLE scan_logs
    ADD sub_job_type NVARCHAR(255) NULL;

    -- เพิ่ม comment อธิบาย column
    EXEC sp_addextendedproperty
        @name = N'MS_Description',
        @value = N'ชื่อประเภทงานย่อย (denormalized copy จาก sub_job_types.sub_job_name สำหรับ query ที่เร็วขึ้น)',
        @level0type = N'SCHEMA', @level0name = N'dbo',
        @level1type = N'TABLE', @level1name = N'scan_logs',
        @level2type = N'COLUMN', @level2name = N'sub_job_type';

    PRINT 'Column sub_job_type has been added to scan_logs table successfully.';
END
ELSE
BEGIN
    PRINT 'Column sub_job_type already exists in scan_logs table.';
END

GO

-- สร้าง index สำหรับ sub_job_type (เพื่อความสอดคล้องกับ job_type ที่มี index อยู่แล้ว)
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_scan_logs_sub_job_type'
    AND object_id = OBJECT_ID('scan_logs')
)
BEGIN
    PRINT 'Creating index IX_scan_logs_sub_job_type...';

    CREATE INDEX IX_scan_logs_sub_job_type ON scan_logs (sub_job_type);

    PRINT 'Index IX_scan_logs_sub_job_type created successfully.';
END
ELSE
BEGIN
    PRINT 'Index IX_scan_logs_sub_job_type already exists.';
END

GO

-- Backfill ข้อมูลเก่า: อัปเดตระเบียนที่มี sub_job_id แต่ยังไม่มี sub_job_type
PRINT 'Backfilling existing records with sub_job_type...';

UPDATE sl
SET sl.sub_job_type = sjt.sub_job_name
FROM scan_logs sl
INNER JOIN sub_job_types sjt ON sl.sub_job_id = sjt.id
WHERE sl.sub_job_id IS NOT NULL
  AND sl.sub_job_type IS NULL;

DECLARE @UpdatedRows INT = @@ROWCOUNT;
PRINT CONCAT('Backfilled ', @UpdatedRows, ' existing records with sub_job_type values.');

GO

PRINT '===========================================';
PRINT 'Migration completed successfully!';
PRINT 'Summary:';
PRINT '- Added sub_job_type NVARCHAR(255) NULL column to scan_logs';
PRINT '- Created index IX_scan_logs_sub_job_type';
PRINT '- Backfilled existing records';
PRINT '===========================================';

GO
