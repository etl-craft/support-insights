ALTER TABLE dwh.ds_agents EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE dwh.ds_agents EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE dwh.ds_agents EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE dwh.ds_customer_types EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE dwh.ds_customer_types EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE dwh.ds_customer_types EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE dwh.ds_support_areas EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE dwh.ds_support_areas EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE dwh.ds_support_areas EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE dwh.ds_sources EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE dwh.ds_sources EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE dwh.ds_sources EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE dwh.info_data_dictionary EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE dwh.info_data_dictionary EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE dwh.info_data_dictionary EXECUTE remove_orphan_files(retention_threshold => '1d');
