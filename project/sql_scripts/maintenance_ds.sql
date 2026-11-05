ALTER TABLE ds.agents EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ds.agents EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ds.agents EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE ds.customer_types EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ds.customer_types EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ds.customer_types EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE ds.support_areas EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ds.support_areas EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ds.support_areas EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE ds.sources EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE ds.sources EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE ds.sources EXECUTE remove_orphan_files(retention_threshold => '1d');
