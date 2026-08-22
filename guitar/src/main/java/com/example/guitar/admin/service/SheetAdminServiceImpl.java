package com.example.guitar.admin.service;

import com.example.guitar.admin.dao.AdminActionLogDao;
import com.example.guitar.admin.dao.SheetAdminDao;
import com.example.guitar.admin.dto.AdminSheetSearchRequest;
import com.example.guitar.admin.model.AdminActionLog;
import com.example.guitar.admin.vo.AdminSheetSummaryResponse;
import com.example.guitar.sheet.model.SheetStatus;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collections;
import java.util.List;

@Service
public class SheetAdminServiceImpl implements SheetAdminService {

    private static final int MAX_REASON_LENGTH = 500;
    private static final int MAX_IP_LENGTH = 45;

    private final SheetAdminDao sheetAdminDao;
    private final AdminActionLogDao adminActionLogDao;

    public SheetAdminServiceImpl(SheetAdminDao sheetAdminDao, AdminActionLogDao adminActionLogDao) {
        this.sheetAdminDao = sheetAdminDao;
        this.adminActionLogDao = adminActionLogDao;
    }

    @Override
    public AdminSheetSearchResult list(AdminSheetSearchRequest request) {
        AdminSheetSearchRequest effectiveRequest = request == null ? new AdminSheetSearchRequest() : request;
        effectiveRequest.normalizeAndValidate();
        long total = sheetAdminDao.countSheets(effectiveRequest);
        List<AdminSheetSummaryResponse> records = sheetAdminDao.findSheets(effectiveRequest);
        if (records == null) {
            records = Collections.emptyList();
        }
        return new AdminSheetSearchResult(records, total, effectiveRequest.getPage(), effectiveRequest.getSize());
    }

    @Override
    @Transactional
    public AdminSheetSummaryResponse offline(long adminUserId, long sheetId, String reason, String ipAddress) {
        validateAdminUserId(adminUserId);
        String normalizedReason = normalizeRequiredReason(reason);
        AdminSheetSummaryResponse current = requireSheetForUpdate(sheetId);
        if (SheetStatus.OFFLINE.name().equals(current.getStatus())) {
            throw conflict("SHEET_ALREADY_OFFLINE", "曲谱已下架");
        }
        if (SheetStatus.DELETED.name().equals(current.getStatus())) {
            throw conflict("SHEET_DELETED", "已删除曲谱不能下架");
        }
        if (!SheetStatus.PUBLISHED.name().equals(current.getStatus())) {
            throw conflict("SHEET_STATE_INVALID", "当前曲谱状态不允许下架");
        }
        if (sheetAdminDao.markOffline(sheetId, adminUserId, normalizedReason) != 1) {
            throw conflict("SHEET_STATE_CONFLICT", "曲谱状态已变化，请刷新后重试");
        }
        insertAudit(adminUserId, "SHEET_OFFLINE", sheetId, normalizedReason,
                SheetStatus.PUBLISHED.name(), SheetStatus.OFFLINE.name(), ipAddress);
        return requireUpdatedSheet(sheetId);
    }

    @Override
    @Transactional
    public AdminSheetSummaryResponse restore(long adminUserId, long sheetId, String ipAddress) {
        validateAdminUserId(adminUserId);
        AdminSheetSummaryResponse current = requireSheetForUpdate(sheetId);
        if (SheetStatus.DELETED.name().equals(current.getStatus())) {
            throw conflict("SHEET_DELETED", "已删除曲谱不能恢复");
        }
        if (!SheetStatus.OFFLINE.name().equals(current.getStatus())) {
            throw conflict("SHEET_NOT_OFFLINE", "仅已下架曲谱可以恢复");
        }
        if (sheetAdminDao.restore(sheetId) != 1) {
            throw conflict("SHEET_STATE_CONFLICT", "曲谱状态已变化，请刷新后重试");
        }
        insertAudit(adminUserId, "SHEET_RESTORE", sheetId, null,
                SheetStatus.OFFLINE.name(), SheetStatus.PUBLISHED.name(), ipAddress);
        return requireUpdatedSheet(sheetId);
    }

    private AdminSheetSummaryResponse requireSheetForUpdate(long sheetId) {
        if (sheetId < 1) {
            throw sheetNotFound();
        }
        AdminSheetSummaryResponse sheet = sheetAdminDao.findByIdForUpdate(sheetId);
        if (sheet == null) {
            throw sheetNotFound();
        }
        return sheet;
    }

    private AdminSheetSummaryResponse requireUpdatedSheet(long sheetId) {
        AdminSheetSummaryResponse sheet = sheetAdminDao.findById(sheetId);
        if (sheet == null) {
            throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "SHEET_UPDATE_FAILED", "曲谱状态更新失败");
        }
        return sheet;
    }

    private void insertAudit(long adminUserId, String actionType, long sheetId, String reason,
                             String beforeState, String afterState, String ipAddress) {
        AdminActionLog actionLog = new AdminActionLog();
        actionLog.setAdminUserId(adminUserId);
        actionLog.setActionType(actionType);
        actionLog.setTargetType("SHEET");
        actionLog.setTargetId(sheetId);
        actionLog.setReason(reason);
        actionLog.setBeforeState(beforeState);
        actionLog.setAfterState(afterState);
        actionLog.setIpAddress(normalizeIpAddress(ipAddress));
        if (adminActionLogDao.insert(actionLog) != 1) {
            throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "ADMIN_AUDIT_FAILED", "管理员操作审计失败");
        }
    }

    private String normalizeRequiredReason(String reason) {
        String normalized = reason == null ? "" : reason.trim();
        if (normalized.isEmpty() || normalized.length() > MAX_REASON_LENGTH) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR",
                    "下架理由长度必须为 1-500 个字符");
        }
        return normalized;
    }

    private String normalizeIpAddress(String ipAddress) {
        if (ipAddress == null) {
            return null;
        }
        String normalized = ipAddress.trim();
        if (normalized.isEmpty()) {
            return null;
        }
        return normalized.length() <= MAX_IP_LENGTH
                ? normalized : normalized.substring(0, MAX_IP_LENGTH);
    }

    private void validateAdminUserId(long adminUserId) {
        if (adminUserId < 1) {
            throw new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录");
        }
    }

    private GuitarApiException sheetNotFound() {
        return new GuitarApiException(HttpStatus.NOT_FOUND, "SHEET_NOT_FOUND", "曲谱不存在");
    }

    private GuitarApiException conflict(String code, String message) {
        return new GuitarApiException(HttpStatus.CONFLICT, code, message);
    }
}
