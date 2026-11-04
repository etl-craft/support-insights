ALTER TABLE ods.interactions EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ods.interactions EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ods.interactions EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE ods.agents EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ods.agents EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ods.agents EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE ods.support_areas EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ods.support_areas EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ods.support_areas EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE ods.customer_types EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ods.customer_types EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ods.customer_types EXECUTE remove_orphan_files(retention_threshold => '1d');
