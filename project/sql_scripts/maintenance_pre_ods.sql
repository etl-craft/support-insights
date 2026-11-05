ALTER TABLE pre_ods.customer_support_stage EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE pre_ods.customer_support_stage EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE pre_ods.customer_support_stage EXECUTE remove_orphan_files(retention_threshold => '1d');
