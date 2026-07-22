package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mybatis.spring.SqlSessionFactoryBean;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.aop.support.AopUtils;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;

import javax.sql.DataSource;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringJUnitConfig(SheetMutationPersistenceIntegrationTest.Config.class)
class SheetMutationPersistenceIntegrationTest {

    @javax.annotation.Resource
    private SheetMutationPersistenceService service;
    @javax.annotation.Resource
    private OssCleanupTaskDao cleanupTaskDao;
    @javax.annotation.Resource
    private DataSource dataSource;
    private JdbcTemplate jdbc;

    @BeforeEach
    void resetDatabase() {
        jdbc = new JdbcTemplate(dataSource);
        jdbc.update("DELETE FROM guitar_oss_cleanup_task");
        jdbc.update("DELETE FROM guitar_favorite");
        jdbc.update("DELETE FROM guitar_sheet_file");
        jdbc.update("DELETE FROM guitar_sheet");
        jdbc.update("DELETE FROM guitar_user");
        jdbc.update("INSERT INTO guitar_user(id, nickname) VALUES (5, 'owner')");
        jdbc.update("INSERT INTO guitar_sheet(id, uploader_id, song_name, singer, sheet_type, difficulty, "
                        + "key_signature, tuning, file_mode, storage_uuid, status, favorite_count) "
                        + "VALUES (8, 5, 'Original Song', 'Singer', 'TAB', 'BEGINNER', 'C', 'Standard', "
                        + "'PDF', 'old-storage', 'OFFLINE', 2)");
        jdbc.update("INSERT INTO guitar_sheet_file(sheet_id, object_key, original_filename, mime_type, "
                        + "file_extension, file_size, sort_order) VALUES (8, 'old.pdf', 'old.pdf', "
                        + "'application/pdf', 'pdf', 10, 1)");
    }

    @Test
    void serviceIsTransactionalProxyAndConstraintFailureRollsBackSheetFilesAndOutbox() {
        assertThat(AopUtils.isAopProxy(service)).isTrue();
        GuitarSheetFile first = replacement("new-1.pdf", 1);
        GuitarSheetFile duplicateOrder = replacement("new-2.pdf", 1);

        assertThatThrownBy(() -> service.replaceFiles(current(), "old-storage", "new-storage",
                FileMode.PDF, Arrays.asList(first, duplicateOrder))).isInstanceOf(RuntimeException.class);

        assertThat(jdbc.queryForObject("SELECT storage_uuid FROM guitar_sheet WHERE id=8", String.class))
                .isEqualTo("old-storage");
        assertThat(jdbc.queryForObject("SELECT object_key FROM guitar_sheet_file WHERE sheet_id=8", String.class))
                .isEqualTo("old.pdf");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM guitar_oss_cleanup_task", Integer.class)).isZero();
    }

    @Test
    void successfulReplacementCommitsFileSwitchAndDiscoverablePendingOutboxTogether() {
        SheetMutationPersistenceService.CleanupOutbox result = service.replaceFiles(current(), "old-storage",
                "new-storage", FileMode.PDF, Arrays.asList(replacement("new.pdf", 1)));

        assertThat(jdbc.queryForObject("SELECT storage_uuid FROM guitar_sheet WHERE id=8", String.class))
                .isEqualTo("new-storage");
        assertThat(jdbc.queryForObject("SELECT object_key FROM guitar_sheet_file WHERE sheet_id=8", String.class))
                .isEqualTo("new.pdf");
        assertThat(result.getTasks()).singleElement().satisfies(task -> assertThat(task.getId()).isNotNull());
        List<OssCleanupTask> due = cleanupTaskDao.findDuePending(LocalDateTime.now().plusMinutes(1), 50);
        assertThat(due).singleElement().extracting(OssCleanupTask::getObjectKey).isEqualTo("old.pdf");
    }

    @Test
    void outboxInsertFailureRollsBackAlreadyAppliedSheetAndFileChanges() {
        jdbc.update("UPDATE guitar_sheet_file SET object_key='outbox-failure.pdf' WHERE sheet_id=8");

        assertThatThrownBy(() -> service.replaceFiles(current(), "old-storage", "new-storage",
                FileMode.PDF, Arrays.asList(replacement("new.pdf", 1))))
                .isInstanceOf(RuntimeException.class);

        assertThat(jdbc.queryForObject("SELECT storage_uuid FROM guitar_sheet WHERE id=8", String.class))
                .isEqualTo("old-storage");
        assertThat(jdbc.queryForObject("SELECT object_key FROM guitar_sheet_file WHERE sheet_id=8", String.class))
                .isEqualTo("outbox-failure.pdf");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM guitar_oss_cleanup_task", Integer.class)).isZero();
    }

    @Test
    void recoveredLeaseRejectsOldWorkerAndAllowsNewClaimGeneration() {
        service.replaceFiles(current(), "old-storage", "new-storage", FileMode.PDF,
                Arrays.asList(replacement("new.pdf", 1)));
        OssCleanupTask task = cleanupTaskDao.findDuePending(LocalDateTime.now().plusMinutes(1), 1).get(0);
        LocalDateTime firstClaim = LocalDateTime.now().plusMinutes(1);

        assertThat(cleanupTaskDao.claimPending(task.getId(), 0L, firstClaim)).isEqualTo(1);
        assertThat(cleanupTaskDao.recoverStaleProcessing(firstClaim.plusMinutes(1), firstClaim.plusMinutes(2)))
                .isEqualTo(1);
        assertThat(cleanupTaskDao.claimPending(task.getId(), 1L, firstClaim.plusMinutes(3))).isEqualTo(1);
        assertThat(cleanupTaskDao.markSuccess(task.getId(), 1L, firstClaim.plusMinutes(4))).isZero();
        assertThat(cleanupTaskDao.markSuccess(task.getId(), 2L, firstClaim.plusMinutes(4))).isEqualTo(1);
    }

    private GuitarSheet current() {
        GuitarSheet sheet = new GuitarSheet();
        sheet.setId(8L); sheet.setUploaderId(5L); sheet.setStorageUuid("old-storage");
        return sheet;
    }

    private GuitarSheetFile replacement(String objectKey, int sortOrder) {
        GuitarSheetFile file = new GuitarSheetFile();
        file.setObjectKey(objectKey); file.setOriginalFilename(objectKey); file.setMimeType("application/pdf");
        file.setFileExtension("pdf"); file.setFileSize(10L); file.setSortOrder(sortOrder);
        return file;
    }

    @Configuration
    @EnableTransactionManagement
    @MapperScan(basePackageClasses = {GuitarSheetDao.class, OssCleanupTaskDao.class})
    static class Config {
        @Bean
        DataSource dataSource() {
            DriverManagerDataSource dataSource = new DriverManagerDataSource();
            dataSource.setDriverClassName("org.h2.Driver");
            dataSource.setUrl("jdbc:h2:mem:sheet_mutation;MODE=MySQL;DB_CLOSE_DELAY=-1;DATABASE_TO_LOWER=TRUE");
            dataSource.setUsername("sa");
            org.springframework.jdbc.datasource.init.ResourceDatabasePopulator populator =
                    new org.springframework.jdbc.datasource.init.ResourceDatabasePopulator(
                            new org.springframework.core.io.ClassPathResource("sheet-mutation-h2.sql"));
            populator.execute(dataSource);
            return dataSource;
        }

        @Bean
        SqlSessionFactory sqlSessionFactory(DataSource dataSource) throws Exception {
            SqlSessionFactoryBean factory = new SqlSessionFactoryBean();
            factory.setDataSource(dataSource);
            factory.setMapperLocations(new PathMatchingResourcePatternResolver()
                    .getResources("classpath*:mapper/**/*.xml"));
            org.apache.ibatis.session.Configuration configuration = new org.apache.ibatis.session.Configuration();
            configuration.setMapUnderscoreToCamelCase(true);
            factory.setConfiguration(configuration);
            return factory.getObject();
        }

        @Bean
        PlatformTransactionManager transactionManager(DataSource dataSource) {
            return new DataSourceTransactionManager(dataSource);
        }

        @Bean
        SheetMutationPersistenceService sheetMutationPersistenceService(
                GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao, OssCleanupTaskDao cleanupTaskDao) {
            return new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        }
    }
}
