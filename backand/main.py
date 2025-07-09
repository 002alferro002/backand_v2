ET', '')

        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API ключи не настроены")

        # Здесь должна быть логика выполнения реальной сделки через Bybit API
        # Пока возвращаем заглушку
        return {
            "status": "success",
            "order_id": "mock_order_123",
            "message": "Сделка выполнена (demo режим)"
        }
    except Exception as e:
        logger.error(f"Ошибка выполнения реальной сделки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/test-connection")
async def test_trading_connection(credentials: dict):
    """Тестирование подключения к торговому API"""
    try:
        api_key = credentials.get('api_key')
        api_secret = credentials.get('api_secret')

        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API ключи не предоставлены")

        # Здесь должна быть проверка подключения к Bybit API
        # Пока возвращаем заглушку
        return {
            "success": True,
            "balance": 10000.0,
            "message": "Подключение успешно (demo режим)"
        }
    except Exception as e:
        logger.error(f"Ошибка тестирования подключения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings/schema")
async def get_settings_schema_endpoint():
    """Получить схему настроек с описаниями и типами"""
    try:
        schema = get_settings_schema()
        return {"schema": schema}
    except Exception as e:
        logger.error(f"Ошибка получения схемы настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
async def update_settings(settings_update: SettingsUpdate):
    """Обновить настройки анализатора"""
    try:
        settings = settings_update.settings
        
        # Преобразуем вложенные настройки в плоский формат
        flat_settings = {}
        for key, value in settings.items():
            # Если это прямой ключ настройки (уже в правильном формате)
            flat_settings[key] = value
        
        # Обновляем все настройки одним вызовом
        success, errors = update_multiple_settings(flat_settings)
        
        if not success:
            return {
                "status": "error", 
                "message": "Ошибка сохранения настроек", 
                "errors": errors
            }

        # Обновляем настройки во всех компонентах системы
        await update_all_components_settings(flat_settings)

        # Уведомляем клиентов об успешном обновлении
        await connection_manager.broadcast_json({
            "type": "settings_updated",
            "status": "success",
            "data": settings,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "message": "Настройки успешно обновлены и сохранены",
            "system_restart_required": False  # Настройки применяются автоматически
        })
        
        logger.info("✅ Настройки успешно обновлены через API")
        return {
            "status": "success", 
            "updated_count": len(flat_settings),
            "message": "Настройки успешно обновлены и сохранены",
            "applied_immediately": True
        }
        
    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}")
        
        # Уведомляем клиентов об ошибке
        if connection_manager:
            await connection_manager.broadcast_json({
                "type": "settings_update_error",
                "error": str(e),
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
            })
        
        return {
            "status": "error", 
            "message": f"Ошибка обновления настроек: {str(e)}", 
            "detail": str(e)
        }


@app.post("/api/settings/reset")
async def reset_settings(reset_data: SettingsReset):
    """Сброс настроек к значениям по умолчанию"""
    try:
        if not reset_data.confirm:
            return {
                "status": "error",
                "message": "Требуется подтверждение для сброса настроек"
            }
        
        success = reset_settings_to_default()
        
        if success:
            # Обновляем настройки во всех компонентах
            from settings import load_settings
            new_settings = load_settings()
            await update_all_components_settings(new_settings)
            
            if connection_manager:
                await connection_manager.broadcast_json({
                    "type": "settings_reset",
                    "status": "success",
                    "message": "Настройки сброшены к значениям по умолчанию",
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
                })
            
            return {
                "status": "success",
                "message": "Настройки успешно сброшены к значениям по умолчанию"
            }
        else:
            return {
                "status": "error",
                "message": "Ошибка сброса настроек"
            }
            
    except Exception as e:
        logger.error(f"Ошибка сброса настроек: {e}")
        return {
            "status": "error",
            "message": f"Ошибка сброса настроек: {str(e)}"
        }


@app.get("/api/settings/export")
async def export_settings_endpoint():
    """Экспорт текущих настроек"""
    try:
        settings = export_settings()
        return {
            "status": "success",
            "settings": settings,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(settings)
        }
    except Exception as e:
        logger.error(f"Ошибка экспорта настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/import")
async def import_settings_endpoint(import_data: SettingsImport):
    """Импорт настроек"""
    try:
        success, errors = import_settings(import_data.settings)
        
        if success:
            # Обновляем настройки во всех компонентах
            await update_all_components_settings(import_data.settings)
            
            if connection_manager:
                await connection_manager.broadcast_json({
                    "type": "settings_imported",
                    "status": "success",
                    "count": len(import_data.settings),
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
                })
            
            return {
                "status": "success",
                "imported_count": len(import_data.settings),
                "message": "Настройки успешно импортированы"
            }
        else:
            return {
                "status": "error",
                "message": "Ошибка импорта настроек",
                "errors": errors
            }
            
    except Exception as e:
        logger.error(f"Ошибка импорта настроек: {e}")
        return {
            "status": "error",
            "message": f"Ошибка импорта настроек: {str(e)}"
        }


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Удалить торговую пару из watchlist"""
    try:
        if not db_queries:
            return {
                "status": "error",
                "message": "База данных недоступна. Настройте подключение в настройках."
            }
            
        await db_queries.remove_from_watchlist(symbol)

        # Удаляем пару из WebSocket менеджера
        if bybit_websocket:
            bybit_websocket.trading_pairs.discard(symbol)
            await bybit_websocket.unsubscribe_from_pairs({symbol})

        # Уведомляем клиентов об обновлении
        await connection_manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "removed",
            "symbol": symbol
        })

        return {"status": "success", "symbol": symbol}
    except Exception as e:
        logger.error(f"Ошибка удаления из watchlist: {e}")
        return {
            "status": "error",
            "message": f"Ошибка удаления из watchlist: {str(e)}"
        }


@app.post("/api/settings/reload")
async def reload_settings_endpoint():
    """Принудительная перезагрузка настроек из .env файла"""
    try:
        from settings import reload_settings, load_settings
        await reload_settings()
        
        # Обновляем настройки во всех компонентах
        new_settings = load_settings()
        await update_all_components_settings(new_settings)

        return {"status": "success", "message": "Настройки перезагружены из .env файла"}
    except Exception as e:
        logger.error(f"Ошибка перезагрузки настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Проверяем существование директории dist перед монтированием
if os.path.exists("dist"):
    if os.path.exists("dist/assets"):
        app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")


    @app.get("/vite.svg")
    async def get_vite_svg():
        if os.path.exists("dist/vite.svg"):
            return FileResponse("dist/vite.svg")
        raise HTTPException(status_code=404, detail="File not found")


    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Обслуживание SPA для всех маршрутов"""
        if os.path.exists("dist/index.html"):
            return FileResponse("dist/index.html")
        raise HTTPException(status_code=404, detail="SPA not built")
else:
    @app.get("/")
    async def root():
        return {"message": "Frontend not built. Run 'npm run build' first."}

if __name__ == "__main__":
    # Настройки сервера из переменных окружения
    host = get_setting('SERVER_HOST', '0.0.0.0')
    port = get_setting('SERVER_PORT', 8000)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )