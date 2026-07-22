package com.example.guitar.admin.service;

import com.example.guitar.admin.dto.AdminSheetSearchRequest;
import com.example.guitar.admin.vo.AdminSheetSummaryResponse;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.jdbc.Sql;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:sheet_admin_test;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "mybatis.mapper-locations=classpath*:mapper/**/*.xml"
})
@Sql(scripts = "/sheet-admin-h2.sql", executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD)
class SheetAdminServiceTest {

    @Autowired
    private SheetAdminService sheetAdminService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void adminCanListEverySheetStateWithStatusFilterAndPaging() {
        insertSheet(102L, "OFFLINE", null);
        insertSheet(103L, "DELETED", "2026-07-21 12:00:00");

        AdminSheetSearchRequest allRequest = request(null, "LATEST", 1, 2);
        SheetAdminService.AdminSheetSearchResult firstPage = sheetAdminService.list(allRequest);

        assertThat(firstPage.getTotal()).isEqualTo(3);
        assertThat(firstPage.getPage()).isEqualTo(1);
        assertThat(firstPage.getSize()).isEqualTo(2);
        assertThat(firstPage.getRecords()).extracting(AdminSheetSummaryResponse::getStatus)
                .containsExactly("DELETED", "OFFLINE");

        SheetAdminService.AdminSheetSearchResult offline =
                sheetAdminService.list(request("offline", "MOST_VIEWED", 1, 20));
        assertThat(offline.getTotal()).isEqualTo(1);
        assertThat(offline.getRecords()).extracting(AdminSheetSummaryResponse::getStatus)
                .containsExactly("OFFLINE");
    }

    @Test
    void invalidStatusSortAndPagingAreRejectedBeforeQuery() {
        assertApiError(() -> sheetAdminService.list(request("archived", "LATEST", 1, 20)),
                "VALIDATION_ERROR", 400);
        assertApiError(() -> sheetAdminService.list(request(null, "DROP_TABLE", 1, 20)),
                "VALIDATION_ERROR", 400);
        assertApiError(() -> sheetAdminService.list(request(null, "LATEST", 0, 20)),
                "VALIDATION_ERROR", 400);
        assertApiError(() -> sheetAdminService.list(request(null, "LATEST", 1, 51)),
                "VALIDATION_ERROR", 400);
    }

    @Test
    void offlineReasonAcceptsTrimmedOneAndFiveHundredCharacterBoundaries() {
        AdminSheetSummaryResponse one = sheetAdminService.offline(7L, 101L, "  理  ", "127.0.0.1");
        assertThat(one.getStatus()).isEqualTo("OFFLINE");
        assertThat(one.getOfflineReason()).isEqualTo("理");

        jdbcTemplate.update("UPDATE guitar_sheet SET status='PUBLISHED', offline_reason=NULL, offline_by=NULL, offline_at=NULL WHERE id=101");
        String maximum = repeat('由', 500);
        AdminSheetSummaryResponse fiveHundred = sheetAdminService.offline(7L, 101L, maximum, "127.0.0.1");
        assertThat(fiveHundred.getOfflineReason()).isEqualTo(maximum);
    }

    @Test
    void blankAndOverlongOfflineReasonsAreRejectedWithoutMutation() {
        assertApiError(() -> sheetAdminService.offline(7L, 101L, "  ", "127.0.0.1"),
                "VALIDATION_ERROR", 400);
        assertApiError(() -> sheetAdminService.offline(7L, 101L, repeat('由', 501), "127.0.0.1"),
                "VALIDATION_ERROR", 400);

        assertThat(sheetStatus(101L)).isEqualTo("PUBLISHED");
        assertThat(auditCount()).isZero();
    }

    @Test
    void offlineUpdatesModerationFieldsAndWritesAccurateAuditRow() {
        AdminSheetSummaryResponse updated =
                sheetAdminService.offline(7L, 101L, "  版权方申请  ", "10.0.0.8");

        assertThat(updated.getStatus()).isEqualTo("OFFLINE");
        assertThat(updated.getOfflineReason()).isEqualTo("版权方申请");
        assertThat(updated.getOfflineBy()).isEqualTo(7L);
        assertThat(updated.getOfflineAt()).isNotNull();
        assertThat(updated.getFavoriteCount()).isEqualTo(3L);

        Map<String, Object> log = onlyAuditRow();
        assertThat(log.get("ADMIN_USER_ID")).isEqualTo(7L);
        assertThat(log.get("ACTION_TYPE")).isEqualTo("SHEET_OFFLINE");
        assertThat(log.get("TARGET_TYPE")).isEqualTo("SHEET");
        assertThat(log.get("TARGET_ID")).isEqualTo(101L);
        assertThat(log.get("REASON")).isEqualTo("版权方申请");
        assertThat(log.get("BEFORE_STATE")).isEqualTo("PUBLISHED");
        assertThat(log.get("AFTER_STATE")).isEqualTo("OFFLINE");
        assertThat(log.get("IP_ADDRESS")).isEqualTo("10.0.0.8");
        assertThat(log.get("CREATE_TIME")).isNotNull();
    }

    @Test
    void restoreClearsModerationFieldsAndWritesAccurateAuditRow() {
        sheetAdminService.offline(7L, 101L, "内容整改", "10.0.0.8");
        jdbcTemplate.update("DELETE FROM guitar_admin_action_log");

        AdminSheetSummaryResponse restored = sheetAdminService.restore(7L, 101L, "10.0.0.9");

        assertThat(restored.getStatus()).isEqualTo("PUBLISHED");
        assertThat(restored.getOfflineReason()).isNull();
        assertThat(restored.getOfflineBy()).isNull();
        assertThat(restored.getOfflineAt()).isNull();
        assertThat(restored.getFavoriteCount()).isEqualTo(3L);

        Map<String, Object> log = onlyAuditRow();
        assertThat(log.get("ACTION_TYPE")).isEqualTo("SHEET_RESTORE");
        assertThat(log.get("BEFORE_STATE")).isEqualTo("OFFLINE");
        assertThat(log.get("AFTER_STATE")).isEqualTo("PUBLISHED");
        assertThat(log.get("REASON")).isNull();
    }

    @Test
    void repeatedAndInvalidTransitionsReturnStableConflictsAndDeletedCannotRestore() {
        assertApiError(() -> sheetAdminService.restore(7L, 101L, "127.0.0.1"),
                "SHEET_NOT_OFFLINE", 409);

        sheetAdminService.offline(7L, 101L, "整改", "127.0.0.1");
        assertApiError(() -> sheetAdminService.offline(7L, 101L, "再次下架", "127.0.0.1"),
                "SHEET_ALREADY_OFFLINE", 409);

        insertSheet(103L, "DELETED", "2026-07-21 12:00:00");
        assertApiError(() -> sheetAdminService.restore(7L, 103L, "127.0.0.1"),
                "SHEET_DELETED", 409);
        assertThat(sheetStatus(103L)).isEqualTo("DELETED");
    }

    @Test
    void missingSheetReturnsNotFoundWithoutAudit() {
        assertApiError(() -> sheetAdminService.offline(7L, 9999L, "不存在", "127.0.0.1"),
                "SHEET_NOT_FOUND", 404);
        assertThat(auditCount()).isZero();
    }

    @Test
    void auditInsertFailureRollsBackSheetStatusUpdate() {
        assertThatThrownBy(() -> sheetAdminService.offline(999L, 101L, "触发审计外键失败", "127.0.0.1"))
                .isInstanceOf(RuntimeException.class);

        assertThat(sheetStatus(101L)).isEqualTo("PUBLISHED");
        assertThat(auditCount()).isZero();
    }

    private AdminSheetSearchRequest request(String status, String sort, int page, int size) {
        AdminSheetSearchRequest request = new AdminSheetSearchRequest();
        request.setStatus(status);
        request.setSort(sort);
        request.setPage(page);
        request.setSize(size);
        return request;
    }

    private void insertSheet(long id, String status, String deletedAt) {
        jdbcTemplate.update("INSERT INTO guitar_sheet (id, uploader_id, song_name, singer, arranger, sheet_type, "
                        + "difficulty, key_signature, capo_position, tuning, status, view_count, favorite_count, "
                        + "create_time, update_time, deleted_at) VALUES (?, 7, ?, '歌手', '编配', 'TAB', "
                        + "'INTERMEDIATE', 'D', 2, 'STANDARD', ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
                id, "曲谱" + id, status, id, deletedAt);
    }

    private String sheetStatus(long id) {
        return jdbcTemplate.queryForObject("SELECT status FROM guitar_sheet WHERE id=?", String.class, id);
    }

    private int auditCount() {
        Integer count = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM guitar_admin_action_log", Integer.class);
        return count == null ? 0 : count;
    }

    private Map<String, Object> onlyAuditRow() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT * FROM guitar_admin_action_log");
        assertThat(rows).hasSize(1);
        return rows.get(0);
    }

    private String repeat(char value, int length) {
        char[] chars = new char[length];
        Arrays.fill(chars, value);
        return new String(chars);
    }

    private void assertApiError(ThrowingCallable action, String code, int status) {
        assertThatThrownBy(action::call).isInstanceOfSatisfying(GuitarApiException.class, exception -> {
            assertThat(exception.getCode()).isEqualTo(code);
            assertThat(exception.getStatus().value()).isEqualTo(status);
        });
    }

    private interface ThrowingCallable {
        void call();
    }
}
