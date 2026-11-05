ALTER TABLE dm.customer_support_fact EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE dm.customer_support_fact EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE dm.customer_support_fact EXECUTE remove_orphan_files(retention_threshold => '1d');
